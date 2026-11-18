import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterAll, test } from "vitest";

import { emailHtml } from "../lib/draftLinks.ts";
import { footerParts } from "../lib/emailFooter.ts";
import { currentUser, profileKey, readProfile, saveProfile } from "../lib/profiles.ts";

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "profiles-"));
afterAll(() => fs.rmSync(tmp, { recursive: true, force: true }));
const DIR = [
  { email: "Dan@Example.org", name: "Dan Elton", role: "admin", projects: [] },
  { email: "rev@example.org", name: "Remy", role: "reviewer", projects: ["p"] },
];
const FOOTER = "Founder and Director, [The Metascience Observatory](https://metascienceobservatory.org)";

test("a footer's links become plain text and HTML, line for line", () => {
  const f = footerParts(`${FOOTER}\n\n<b>x</b> & [bad](javascript:alert(1))\n\n`);
  assert.deepEqual(f.plain, ["Founder and Director, The Metascience Observatory", "", "<b>x</b> & [bad](javascript:alert(1))"]);
  assert.equal(f.html[0], 'Founder and Director, <a href="https://metascienceobservatory.org">The Metascience Observatory</a>');
  assert.equal(f.html[2], "&lt;b&gt;x&lt;/b&gt; &amp; [bad](javascript:alert(1))", "only http(s) links; the rest escaped");
  assert.deepEqual(footerParts(""), { plain: [], html: [] });
});

test("profiles are keyed by the signed-in email, else by the directory's email for the name", () => {
  assert.equal(profileKey({ email: "Rev@Example.org" }, DIR), "rev@example.org");
  assert.equal(profileKey({ name: "dan elton" }, DIR), "dan@example.org");
  assert.equal(profileKey({ name: "Visitor" }, DIR), "name:Visitor");
  assert.equal(profileKey({ name: " " }, DIR), null);
  // Hosted: the sign-in decides, whatever name the body sends.
  assert.deepEqual(currentUser({ email: "rev@example.org", name: "Remy" }, "Dan Elton", DIR), { name: "Remy", key: "rev@example.org" });
  // Local: the chip's name, else the directory's admin.
  assert.deepEqual(currentUser(null, "", DIR), { name: "Dan Elton", key: "dan@example.org" });
});

test("a profile is saved and read back; an overlong footer is refused", () => {
  const file = path.join(tmp, "profiles.json");
  assert.equal(readProfile("dan@example.org", file).email_footer, "");
  saveProfile("dan@example.org", { email_footer: FOOTER }, file);
  saveProfile("rev@example.org", { email_footer: "Reviewer" }, file);
  assert.equal(readProfile("dan@example.org", file).email_footer, FOOTER);
  assert.equal(readProfile("rev@example.org", file).email_footer, "Reviewer");
  assert.throws(() => saveProfile("x", { email_footer: "y".repeat(1001) }, file), /longer than 1000/);
});

test("the formatted email links the footer's text where the plain body has it", () => {
  const f = footerParts(FOOTER);
  const html = emailHtml("Dear Editors,\n\nText.\n\nBest regards,\nDan Elton\n" + f.plain[0], null, f);
  assert.match(html, /<p>Best regards,<br>Dan Elton<br>Founder and Director, <a href="https:\/\/metascienceobservatory.org">The Metascience Observatory<\/a><\/p>$/);
});

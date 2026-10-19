import assert from 'node:assert/strict';
import {extractEmails} from '../lib/emails.ts';

assert.deepEqual(extractEmails(['Correspondence: J.Smith@Uni.Edu; b-jones@med.example.ac.uk.']),
  ['j.smith@uni.edu', 'b-jones@med.example.ac.uk']);
assert.deepEqual(extractEmails(['{alice, bob.c}@lab.org']), ['alice@lab.org', 'bob.c@lab.org']);
// pdf.js runs split around the @ and the final dot.
assert.deepEqual(extractEmails(['smith @ harvard .edu']), ['smith@harvard.edu']);
assert.deepEqual(extractEmails(['mailto:x@y.com', 'X@Y.com again']), ['x@y.com']);
assert.deepEqual(extractEmails(['jane [at] inst [dot] fr']), ['jane@inst.fr']);
// Not addresses: a figure file name, a bare @ handle, sentence punctuation.
assert.deepEqual(extractEmails(['logo@2x.png', 'follow @lab on X']), []);
// A sentence after an address is not glued onto its domain.
assert.deepEqual(extractEmails(['a@uni.edu. Co-authors: b@x.org. co', 'c@uni. edu']), ['a@uni.edu', 'b@x.org', 'c@uni.edu']);
console.log('Email extraction: plain, grouped, split runs, mailto, obfuscated, non-address rejection passed');
// A paper with only publisher XML: tagged addresses, mailto links, then text.
import {xmlEmails} from '../lib/emails.ts';
assert.deepEqual(xmlEmails('<article><front><corresp id="FN1">Corresponding author. Tel.: +1. <email>ssamal@umd.edu</email></corresp></front></article>'), ['ssamal@umd.edu']);
assert.deepEqual(xmlEmails('<ce:e-address type="email" xlink:href="mailto:A.B@Uni.EDU">A.B@Uni.EDU</ce:e-address>'), ['a.b@uni.edu']);
assert.deepEqual(xmlEmails('<ext-link xlink:href="mailto:x%2By@lab.org">write</ext-link><p>or z&#64;lab.org &amp; more</p>'), ['x+y@lab.org', 'z@lab.org']);
assert.deepEqual(xmlEmails('<graphic xlink:href="logo@2x.png"/><p>no address</p>'), []);
console.log('XML email extraction: JATS, Elsevier, mailto and text passed');

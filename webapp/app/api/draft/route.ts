import { rejectCrossOrigin } from "@/lib/mutation";
import { NextResponse } from "next/server";
import fsp from "node:fs/promises";
import path from "node:path";

import { errMsg } from "@/lib/err";
import { pyJson } from "@/lib/python";
import { paperAbsDir } from "@/lib/store";

export const dynamic = "force-dynamic";

/** Generate a PubPeer/letter draft from STORED findings. The server never
 * posts anywhere; the human copies the text out themselves. */
export async function POST(req: Request) {
  const rejected = rejectCrossOrigin(req); if (rejected) return rejected;
  const body = await req.json().catch(() => ({}));
  const { project, dir, kind, finding_ids } = body as {
    project?: string; dir?: string; kind?: string; finding_ids?: string[];
  };
  if (!project || !dir || !kind) {
    return NextResponse.json({ error: "project, dir, kind required" },
                             { status: 400 });
  }
  try {
    const abs = await paperAbsDir(project, dir);
    const verb = kind === "letter" ? "draft-letter" : "draft-pubpeer";
    const args = [verb, abs, "--json"];
    if (finding_ids?.length) args.push("--findings", finding_ids.join(","));
    // Draft generation is a paid model call; give it its own generous
    // timeout rather than raising the global pyJson one.
    const rec = await pyJson(args, { timeoutMs: 300_000 }) as {
      ok?: boolean; error?: string; path?: string; body?: string;
    };
    if (!rec.ok) {
      return NextResponse.json({ error: rec.error || "draft failed" },
                               { status: 502 });
    }
    return NextResponse.json(rec);
  } catch (e) {
    return NextResponse.json({ error: errMsg(e) }, { status: 500 });
  }
}

export async function GET(req: Request) {
  const url = new URL(req.url);
  const project = url.searchParams.get("project") || "";
  const dir = url.searchParams.get("dir") || "";
  const file = url.searchParams.get("f") || "";
  if (!project || !dir) {
    return NextResponse.json({ error: "project and dir required" },
                             { status: 400 });
  }
  try {
    const abs = await paperAbsDir(project, dir);
    if (file) {
      if (file.includes("/") || file.includes("..")) {
        return NextResponse.json({ error: "bad file" }, { status: 400 });
      }
      const body = await fsp.readFile(path.join(abs, "drafts", file), "utf8");
      return NextResponse.json({ name: file, body });
    }
    const names = await fsp.readdir(path.join(abs, "drafts")).catch(() => []);
    return NextResponse.json({
      drafts: names.filter((n) => n.endsWith(".md")).sort(),
    });
  } catch (e) {
    return NextResponse.json({ error: errMsg(e) }, { status: 500 });
  }
}

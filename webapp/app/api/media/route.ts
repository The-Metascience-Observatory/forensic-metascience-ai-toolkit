import { NextResponse } from "next/server";
import fs from "node:fs";
import fsp from "node:fs/promises";
import { Readable } from "node:stream";
import { errMsg } from "@/lib/err";
import { byteRange } from "@/lib/byteRange";
import { cacheControl, mediaDisposition, mediaType } from "@/lib/media";
import { workbenchTimed, serverTiming } from "@/lib/workbench";


export const dynamic = "force-dynamic";

export async function GET(req: Request) { return serve(req, false); }

export async function HEAD(req: Request) { return serve(req, true); }

async function serve(req: Request, head: boolean) {
  const url = new URL(req.url);
  const project = url.searchParams.get("project") || "";
  const component = url.searchParams.get("component") || "";
  const dir = url.searchParams.get("dir") || "";
  const file = url.searchParams.get("f") || "";
  if (!project || !dir || !file) return NextResponse.json({ error: "project, dir, f required" }, { status: 400 });
  try {
    const variant = url.searchParams.get("variant");
    if (variant && variant !== "thumbnail") return NextResponse.json({ error: "Unknown media variant" }, { status: 400 });
    let {value:resolved,timings} = await workbenchTimed("artifact", {component, project, dir, f: file, variant}, {signal:req.signal});
    if (variant === "thumbnail" && !resolved.thumbnail_ready) {
      const generated=await workbenchTimed("thumbnail", {component, project, dir, f: file}, {signal:req.signal});
      resolved=generated.value;
      for(const [key,value] of Object.entries(generated.timings))timings[key]=(timings[key] || 0)+value;
    }
    const abs = resolved.path;
    const mediaName = resolved.record.name;
    const st = await fsp.stat(abs);
    const etag = `"${st.size.toString(16)}-${st.mtimeMs.toString(16)}-${st.ctimeMs.toString(16)}"`;
    const modified = st.mtime.toUTCString();
    const headers: Record<string, string> = {
      "Content-Type": mediaType(mediaName),
      "Server-Timing": serverTiming(timings),
      "Content-Disposition": mediaDisposition(mediaName, url.searchParams.get("download") === "1"),
      "Accept-Ranges": "bytes", "Cache-Control": cacheControl(file, variant),
      "ETag": etag, "Last-Modified": modified,
      "X-Content-Type-Options": "nosniff",
      ...(mediaType(mediaName).startsWith("text/html") ? {
        "Content-Security-Policy": "sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'",
      } : {}),
    };
    const noneMatch = req.headers.get("if-none-match");
    if ((noneMatch && (noneMatch === "*" || noneMatch.split(",").some((s) => s.trim().replace(/^W\//, "") === etag)))
        || (!noneMatch && req.headers.get("if-modified-since") === modified)) {
      return new NextResponse(null, { status: 304, headers });
    }
    const ifRange = req.headers.get("if-range");
    const range = byteRange(!ifRange || ifRange === etag || ifRange === modified ? req.headers.get("range") : null, st.size);
    if (range === false) return new NextResponse(null, { status: 416, headers: { ...headers, "Content-Range": `bytes */${st.size}` } });
    headers["Content-Length"] = String(range ? range.end - range.start + 1 : st.size);
    if (range) headers["Content-Range"] = `bytes ${range.start}-${range.end}/${st.size}`;
    if (head) return new NextResponse(null, { status: range ? 206 : 200, headers });
    const stream = fs.createReadStream(abs, range || undefined);
    const abort = () => stream.destroy();
    req.signal.addEventListener("abort", abort, { once: true });
    stream.on("close", () => req.signal.removeEventListener("abort", abort));
    return new NextResponse(Readable.toWeb(stream) as ReadableStream, { status: range ? 206 : 200, headers });
  } catch (e) {
    return NextResponse.json({ error: errMsg(e) }, { status: 404 });
  }
}

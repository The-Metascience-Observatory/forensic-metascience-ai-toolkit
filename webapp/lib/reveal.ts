import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { promisify } from "node:util";

/** Fallback file-browser command for "show this paper in a folder".
 *
 * Pure argv construction, exported so the smoke test can pin each platform
 * without spawning anything. Windows and macOS can SELECT the file;
 * Linux first uses FileManager1 (Caja, Nautilus, Dolphin, etc.) to select the
 * file. xdg-open is the folder-only fallback when that service is unavailable.
 */
export function revealArgv(
  platform: NodeJS.Platform, dirAbs: string, fileAbs: string | null,
): string[] {
  if (platform === "win32") {
    return fileAbs ? ["explorer", `/select,${fileAbs}`] : ["explorer", dirAbs];
  }
  if (platform === "darwin") {
    return fileAbs ? ["open", "-R", fileAbs] : ["open", dirAbs];
  }
  return ["xdg-open", dirAbs];
}

export function linuxRevealArgv(dirAbs: string, fileAbs: string | null): string[] {
  return ["gdbus", "call", "--session", "--dest", "org.freedesktop.FileManager1",
    "--object-path", "/org/freedesktop/FileManager1", "--method",
    `org.freedesktop.FileManager1.${fileAbs ? "ShowItems" : "ShowFolders"}`,
    JSON.stringify([pathToFileURL(fileAbs || dirAbs).href]), ""];
}

const exec = promisify(execFile);
export async function runRevealCommand(argv: string[]): Promise<void> {
  const env = {...process.env};
  if (process.platform === "linux" && !env.DBUS_SESSION_BUS_ADDRESS && process.getuid) {
    const bus = `${env.XDG_RUNTIME_DIR || `/run/user/${process.getuid()}`}/bus`;
    if (existsSync(bus)) env.DBUS_SESSION_BUS_ADDRESS = `unix:path=${bus}`;
  }
  // Wait for the launcher/desktop service's acknowledgment. ENOENT and
  // nonzero exits must reach the UI rather than returning an unconditional OK.
  await exec(argv[0], argv.slice(1), {env, timeout: 5000, maxBuffer: 8192, windowsHide: true});
}

export async function revealLocation(platform: NodeJS.Platform, directory: string, file: string | null,
  run: (argv: string[]) => Promise<void> = runRevealCommand): Promise<{selected: boolean}> {
  let desktopError = "";
  if (platform === "linux") {
    try {
      await run(linuxRevealArgv(directory, file));
      return {selected: !!file};
    } catch (error) {
      desktopError = `Desktop file-manager service: ${String(error)}. `;
    }
  }
  try {
    await run(revealArgv(platform, directory, file));
    return {selected: !!file && (platform === "darwin" || platform === "win32")};
  } catch (error) {
    throw new Error(`Could not open the file browser. ${desktopError}${String(error)}`);
  }
}

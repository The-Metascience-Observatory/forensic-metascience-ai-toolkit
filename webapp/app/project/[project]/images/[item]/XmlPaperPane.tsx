"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import useSWR from "swr";
import type { Item, Panel } from "@/app/images/lib";
import { HtmlArticlePane } from "../../review/[slug]/HtmlArticlePane";
import { NativeImagePane } from "./NativeImagePane";
import { panelFigure, type XmlFigure } from "@/lib/xmlFigures";
import { getJson } from "@/lib/getJson";
import { imageXmlBoxes, type ImageSize } from "@/lib/imageXmlBoxes";

type Source = { article: { mode: string; html?: string; warning?: string; figures?: XmlFigure[] }; error?: string };
type SourceKey = ["source", string, string, string, string];

async function fetchSource([, project, dir, run, component]: SourceKey): Promise<Source> {
  const query = new URLSearchParams({ method: "source", project, dir, run, component });
  const source = await getJson<Source>(`/api/workbench?${query}`).catch((error: unknown) => {
    throw new Error((error instanceof Error && error.message) || "Paper could not be loaded");
  });
  if (source.error) throw new Error(source.error);
  return source;
}

/** Independent loading keeps the comparator and review decisions immediately usable. */
export function XmlPaperPane({
  project,
  panel,
  run,
  component,
  revision,
  reason,
  item,
  sizes,
}: {
  project: string;
  panel: Panel;
  run: string;
  component: string;
  revision?: string;
  reason: string;
  item?: Item;
  sizes?: (ImageSize | null)[];
}) {
  const key: SourceKey = ["source", project, panel.paper_dir, run, component];
  const [navigation, setNavigation] = useState<{ key: string; anchor: string; nonce: number }>();
  const [native, setNative] = useState<string>();
  const [showBoxes, setShowBoxes] = useState(true);
  const panelKey = `${key.join("\u0000")}:${panel.uid}`;
  // Reuse the article immediately between findings, but revalidate sources
  // on navigation, focus and while visible so changed files cannot stay hidden.
  const { data, error, mutate } = useSWR<Source, Error>(key, fetchSource, {
    refreshInterval: 30000,
    revalidateOnFocus: true,
    refreshWhenHidden: false,
  });
  const seenRevision = useRef(revision);
  useEffect(() => {
    if (seenRevision.current === revision) return;
    seenRevision.current = revision;
    void mutate();
  }, [revision, mutate]);
  const current =
    data || error ? { source: error ? undefined : data, error: error?.message } : undefined;
  const article = current?.source?.article;
  const figures = useMemo(() => article?.figures || [], [article]);
  const boxes = useMemo(
    () => (item ? imageXmlBoxes(item, panel.paper_dir, figures, sizes) : []),
    [item, panel.paper_dir, figures, sizes],
  );
  const selected = panelFigure(panel, figures);
  const anchor = navigation?.key === panelKey ? navigation.anchor : selected?.anchor;
  // The rendition of the selected figure this panel's box is drawn on.
  const side =
    item?.panels.findIndex((p) => p.uid === panel.uid && p.paper_dir === panel.paper_dir) ?? -1;
  const image = boxes.find((b) => b.side === side && b.anchor === anchor)?.relpath;
  const showXml = article?.mode === "xml" && article.html;
  if (!current)
    return (
      <p role="status" className="muted" style={{ padding: 12 }}>
        Loading paper…
      </p>
    );
  if (!showXml)
    return (
      <>
        <p role="status" className="muted" style={{ padding: "0 12px" }}>
          {current.error || article?.warning || "XML paper unavailable."}
        </p>
        <NativeImagePane
          item={item}
          project={project}
          panel={panel}
          documentPath={panel.document?.path || null}
          reason={reason}
        />
      </>
    );
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", minHeight: 0 }}>
      <div className="xml-navigation">
        <strong>XML paper</strong>
        <label>
          Figure{" "}
          <select
            aria-label="Article figure"
            value={anchor || ""}
            onChange={(e) => {
              setNative(undefined);
              setNavigation({
                key: panelKey,
                anchor: e.target.value,
                nonce: (navigation?.nonce || 0) + 1,
              });
            }}
          >
            <option value="">Article beginning</option>
            {figures.map((f) => (
              <option key={f.anchor} value={f.anchor}>
                {f.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={() => {
            setNative(undefined);
            setNavigation({ key: panelKey, anchor: "", nonce: (navigation?.nonce || 0) + 1 });
          }}
        >
          Back to top
        </button>
        <button type="button" onClick={() => setNative(native === panelKey ? undefined : panelKey)}>
          {native === panelKey ? "Show article" : "Show native image"}
        </button>
        {boxes.length > 0 && native !== panelKey && (
          <label title="Solid: matched region. Dashed: whole panel; match not localized.">
            <input
              type="checkbox"
              checked={showBoxes}
              onChange={(e) => setShowBoxes(e.target.checked)}
            />{" "}
            Show boxes
          </label>
        )}
      </div>
      {article.warning && <p className="muted xml-source-note">{article.warning}</p>}
      {!selected && (
        <p className="muted xml-source-note">
          The selected panel could not be uniquely linked to an XML figure. Use the figure list or
          native image.
        </p>
      )}
      {native === panelKey ? (
        <NativeImagePane
          item={item}
          project={project}
          panel={panel}
          documentPath={panel.document?.path || null}
          reason={reason}
        />
      ) : (
        <HtmlArticlePane
          html={article.html!}
          className="xml-article"
          figureAnchor={anchor || ""}
          figureImage={image}
          imageBoxes={showBoxes ? boxes : undefined}
          jumpNonce={`${panelKey}:${navigation?.nonce || 0}`}
        />
      )}
    </div>
  );
}

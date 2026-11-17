"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  ComponentPropsWithoutRef,
  KeyboardEvent as ReactKeyboardEvent,
  MouseEvent as ReactMouseEvent,
  PointerEvent as ReactPointerEvent,
} from "react";

export type ColumnResizeOptions = {
  storageKey?: string;
  def: number;
  min: number;
  max: number;
  label?: string;
};

export type ColumnResize = {
  width: number;
  isDragging: boolean;
  reset: () => void;
  setWidth: (width: number) => void;
  getHandleProps: (labelOverride?: string) => ComponentPropsWithoutRef<"div">;
};

function readWidth(key: string, def: number, min: number, max: number): number {
  if (typeof window === "undefined") return def;
  try {
    const val = window.localStorage.getItem(key);
    if (val != null) {
      const n = Number(val);
      if (Number.isFinite(n) && n >= min && n <= max) return n;
    }
  } catch {
    /* localStorage blocked or unavailable */
  }
  return def;
}

function storeWidth(key: string, width: number): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, String(Math.round(width)));
  } catch {
    /* localStorage blocked or unavailable */
  }
}

export function useColumnResize({
  storageKey,
  def,
  min,
  max,
  label = "Resize column",
}: ColumnResizeOptions): ColumnResize {
  const [width, setWidth] = useState(def);
  const [isDragging, setIsDragging] = useState(false);
  const widthRef = useRef(def);
  const dragStartRef = useRef<{ startX: number; startWidth: number; pointerId: number } | null>(
    null,
  );

  useEffect(() => {
    if (!storageKey) return;
    const n = readWidth(storageKey, def, min, max);
    if (n !== widthRef.current) {
      widthRef.current = n;
      setWidth(n);
    }
  }, [storageKey, def, min, max]);

  const apply = useCallback(
    (next: number) => {
      const clamped = Math.max(min, Math.min(max, Math.round(next)));
      widthRef.current = clamped;
      setWidth(clamped);
      return clamped;
    },
    [min, max],
  );

  const reset = useCallback(() => {
    apply(def);
    if (storageKey) storeWidth(storageKey, def);
  }, [apply, def, storageKey]);

  const onPointerDown = useCallback((e: ReactPointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.focus();
    dragStartRef.current = {
      startX: e.clientX,
      startWidth: widthRef.current,
      pointerId: e.pointerId,
    };
    setIsDragging(true);
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {
      /* ignore if pointer capture fails */
    }
  }, []);

  const onPointerMove = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      if (!dragStartRef.current) return;
      const delta = e.clientX - dragStartRef.current.startX;
      apply(dragStartRef.current.startWidth + delta);
    },
    [apply],
  );

  const onPointerUp = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      if (!dragStartRef.current) return;
      try {
        e.currentTarget.releasePointerCapture(dragStartRef.current.pointerId);
      } catch {
        /* already released */
      }
      dragStartRef.current = null;
      setIsDragging(false);
      if (storageKey) storeWidth(storageKey, widthRef.current);
    },
    [storageKey],
  );

  const onKeyDown = useCallback(
    (e: ReactKeyboardEvent<HTMLDivElement>) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight" && e.key !== "Home" && e.key !== "End") {
        return;
      }
      e.preventDefault();
      e.stopPropagation();
      const step = e.shiftKey ? 20 : 10;
      let next = widthRef.current;
      if (e.key === "ArrowLeft") next -= step;
      else if (e.key === "ArrowRight") next += step;
      else if (e.key === "Home") next = min;
      else if (e.key === "End") next = max;
      apply(next);
      if (storageKey) storeWidth(storageKey, widthRef.current);
    },
    [apply, min, max, storageKey],
  );

  const onDoubleClick = useCallback(
    (e: ReactMouseEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      reset();
    },
    [reset],
  );

  const getHandleProps = useCallback(
    (labelOverride?: string): ComponentPropsWithoutRef<"div"> => ({
      role: "separator",
      "aria-orientation": "vertical",
      "aria-label": labelOverride || label,
      "aria-valuenow": Math.round(width),
      "aria-valuemin": min,
      "aria-valuemax": max,
      tabIndex: 0,
      className: `col-resize-handle${isDragging ? " dragging" : ""}`,
      title: "Drag to resize column (double-click to reset)",
      onPointerDown,
      onPointerMove,
      onPointerUp,
      onPointerCancel: onPointerUp,
      onKeyDown,
      onDoubleClick,
    }),
    [
      width,
      min,
      max,
      isDragging,
      label,
      onPointerDown,
      onPointerMove,
      onPointerUp,
      onKeyDown,
      onDoubleClick,
    ],
  );

  return {
    width,
    isDragging,
    reset,
    setWidth: apply,
    getHandleProps,
  };
}

import { projectXmlImageBox, type XmlImageBox } from './imageXmlBoxes.ts';

import { appendFlipArrow, boxCorners } from './flipArrow.ts';

const NS = 'http://www.w3.org/2000/svg';

/** Attach overlays to the actual article images, including lazy-loaded ones.
 * The wrapper shares the image's layout, so resizing needs no cached DOM boxes.
 */
export function mountXmlImageOverlays(root: HTMLElement, boxes: XmlImageBox[]): () => void {
  const cleanup: (() => void)[] = [];
  for (const figure of root.querySelectorAll<HTMLElement>('figure[id]')) {
    for (const image of figure.querySelectorAll<HTMLImageElement>('img')) {
      const ref = new URL(image.src, document.baseURI).searchParams.get('f');
      const targets = boxes.filter(b => b.anchor === figure.id && b.relpath === ref);
      if (!targets.length) continue;
      let wrapper: HTMLSpanElement | undefined;
      const clear = () => {
        if (wrapper) {
          wrapper.querySelector('svg')?.remove();
          wrapper.replaceWith(...Array.from(wrapper.childNodes));
          wrapper = undefined;
        }
      };
      const paint = () => {
        clear();
        if (!image.isConnected || !image.naturalWidth || !image.naturalHeight) return;
        const projected = targets.map(box => ({ box, rect: projectXmlImageBox(box, [image.naturalWidth, image.naturalHeight]) }))
          .filter((p): p is { box: XmlImageBox; rect: number[] } => p.rect !== null);
        if (!projected.length) return;
        wrapper = document.createElement('span');
        wrapper.className = 'xml-image-overlay';
        image.replaceWith(wrapper);
        wrapper.append(image);
        const svg = document.createElementNS(NS, 'svg');
        svg.setAttribute('viewBox', `0 0 ${image.naturalWidth} ${image.naturalHeight}`);
        svg.setAttribute('aria-label', 'Image comparison locations');
        svg.setAttribute('role', 'img');
        for (const { box, rect: [x0, y0, x1, y1] } of projected) {
          const group = document.createElementNS(NS, 'g');
          group.dataset.boxId = box.id;
          group.dataset.boxKind = box.kind;
          const title = document.createElementNS(NS, 'title');
          title.textContent = box.kind === 'match' ? `Matched region ${box.label}` : `Panel ${box.label}; match not localized`;
          group.append(title);
          for (const [stroke, width] of [['#101820', '5'], [box.color, '2.5']]) {
            const rect = document.createElementNS(NS, 'rect');
            for (const [k, v] of Object.entries({ x: x0, y: y0, width: x1 - x0, height: y1 - y0,
              fill: 'none', stroke, 'stroke-width': width, 'vector-effect': 'non-scaling-stroke' })) rect.setAttribute(k, String(v));
            if (box.kind === 'panel') rect.setAttribute('stroke-dasharray', '6 4');
            group.append(rect);
          }
          appendFlipArrow(group, boxCorners([x0,y0,x1,y1]), box.color, box.flipDirection);
          const label = document.createElementNS(NS, 'text');
          label.setAttribute('x', String(x0 + 3));
          label.setAttribute('y', String(Math.max(16, y0 - 5)));
          label.setAttribute('fill', box.color);
          label.setAttribute('stroke', '#101820');
          label.setAttribute('stroke-width', '3');
          label.setAttribute('paint-order', 'stroke');
          label.setAttribute('font-size', '16');
          label.setAttribute('font-weight', 'bold');
          label.textContent = box.label;
          group.append(label);
          svg.append(group);
        }
        wrapper.append(svg);
      };
      image.addEventListener('load', paint);
      image.addEventListener('error', clear);
      if (image.complete) paint();
      cleanup.push(() => { image.removeEventListener('load', paint); image.removeEventListener('error', clear); clear(); });
    }
  }
  return () => cleanup.forEach(fn => fn());
}

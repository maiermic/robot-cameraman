function rgbToHex(r, g, b) {
  const rgbHex =
    [r, g, b]
      .map(value => Math.round(value * 255).toString(16))
      .map(value => value.length > 1 ? value : '0' + value)
      .join('');
  return '#' + rgbHex.toUpperCase();
}

/**
 * Converts an HSV color value to RGB. Conversion formula
 * adapted from http://en.wikipedia.org/wiki/HSV_color_space.
 *
 * @param h {Number} The hue contained in the set [0, 360]
 * @param s {Number} The saturation contained in the set [0, 100]
 * @param v {Number} The value contained in the set [0, 100]
 * @return {string} The RGB representation in hex format, e.g. `#00BEEF`
 * @see https://gist.github.com/mjackson/5311256
 */
export function hsvToRgbHex(h, s, v) {
  h /= 360
  s /= 100
  v /= 100

  const i = Math.floor(h * 6);
  const f = h * 6 - i;
  const p = v * (1 - s);
  const q = v * (1 - f * s);
  const t = v * (1 - (1 - f) * s);
  switch (i % 6) {
    case 0:
      return rgbToHex(v, t, p);
    case 1:
      return rgbToHex(q, v, p);
    case 2:
      return rgbToHex(p, v, t);
    case 3:
      return rgbToHex(p, q, v);
    case 4:
      return rgbToHex(t, p, v);
    case 5:
      return rgbToHex(v, p, q);
  }
}

/**
 * Converts an RGB color value to HSV. Conversion formula
 * adapted from http://en.wikipedia.org/wiki/HSV_color_space.
 *
 * @param r {Number} The red color value contained in the set [0, 255]
 * @param g {Number} The green color value contained in the set [0, 255]
 * @param b {Number} The blue color value contained in the set [0, 255]
 * @return {{h: Number, s: Number, v: Number}} The HSV representation,
 * where h is contained in the set [0, 360] and
 * s and v are contained in the set [0, 100].
 *
 * @see https://gist.github.com/mjackson/5311256
 */
function rgbToHsv(r, g, b) {
  r /= 255
  g /= 255
  b /= 255

  const max = Math.max(r, g, b), min = Math.min(r, g, b);

  const d = max - min;
  let s = max === 0 ? 0 : d / max;

  let h;
  if (max === min) {
    h = 0; // achromatic
  } else {
    switch (max) {
      case r:
        h = (g - b) / d + (g < b ? 6 : 0);
        break;
      case g:
        h = (b - r) / d + 2;
        break;
      case b:
        h = (r - g) / d + 4;
        break;
    }
    h /= 6;
  }
  h *= 360
  s *= 100
  const v = max * 100;
  return {h, s, v};
}

/**
 * @param rgbHex {string} RGB color in hex format, e.g. `#00BEEF`
 * @return {{h: Number, s: Number, v: Number}} The HSV representation,
 * where h is contained in the set [0, 360] and
 * s and v are contained in the set [0, 100].
 */
export function rgbHexToHsv(rgbHex) {
  const {r, g, b} = parseRgbHex(rgbHex);
  return rgbToHsv(r, g, b)
}

export function parseRgbHex(rgbHex) {
  if (!(rgbHex.length === 7 && rgbHex[0] === '#')) {
    throw Error(`Unexpected color ${rgbHex}`)
  }
  return {
    r: Number.parseInt(rgbHex.substring(1, 3), 16),
    g: Number.parseInt(rgbHex.substring(3, 5), 16),
    b: Number.parseInt(rgbHex.substring(5, 7), 16),
  }
}

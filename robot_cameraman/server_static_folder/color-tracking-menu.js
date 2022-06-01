import {configurationRequestQueue, getJson, putJson} from "./api.js";

const template = document.createElement('template')
template.innerHTML = `
<x-color-picker id="minimumColor" color="hsv(0, 0, 0)">
    <span slot="title">Minimum</span>
</x-color-picker>
<x-color-picker id="maximumColor" color="hsv(359, 100, 100)">
    <span slot="title">Maximum</span>
</x-color-picker>
`

function apiToAttributeColor([h, s, v]) {
  return JSON.stringify({
    h: Math.round(h / 255 * 360),
    s: Math.round(s / 255 * 100),
    v: Math.round(v / 255 * 100),
  })
}

function toApiColor({h, s, v}) {
  return [
    Math.round(h / 360 * 255),
    Math.round(s / 100 * 255),
    Math.round(v / 100 * 255),
  ]
}

class ColorTrackingMenu extends HTMLElement {
  constructor() {
    super().attachShadow({mode: 'open'});
  }

  async connectedCallback() {
    // noinspection ES6MissingAwait
    putJson('/api/live-view/source', 'COLOR_MASK')
    const {
      tracking: {
        color: {
          min_hsv,
          max_hsv,
        }
      }
    } = await getJson('/api/configuration');
    const node = template.content.cloneNode(true);
    this.minimumColorListener = this._setColorAndListener({
      element: node.getElementById('minimumColor'),
      color: min_hsv,
      configurationKey: 'min_hsv',
    })
    this.maximumColorListener = this._setColorAndListener({
      element: node.getElementById('maximumColor'),
      color: max_hsv,
      configurationKey: 'max_hsv',
    })
    this.shadowRoot.append(node)
  }

  /**
   * @param element {ColorPicker}
   * @param color {Array}
   * @param configurationKey {string}
   * @private
   */
  _setColorAndListener({element, color, configurationKey}) {
    element.setAttribute('color', apiToAttributeColor(color))
    const listener = () => {
      // noinspection JSIgnoredPromiseFromCall
      configurationRequestQueue.add({
        tracking: {
          color: {
            [configurationKey]: toApiColor(element.color),
          }
        }
      });
    };
    element.addEventListener('input', listener)
    return listener
  }

  disconnectedCallback() {
    // noinspection JSIgnoredPromiseFromCall
    putJson('/api/live-view/source', 'LIVE_VIEW')
    if (this.minimumColorListener) {
      this.shadowRoot
        .getElementById('minimumColor')
        ?.removeEventListener('input', this.minimumColorListener)
      this.minimumColorListener = null
    }
    if (this.maximumColorListener) {
      this.shadowRoot
        .getElementById('minimumColor')
        ?.removeEventListener('input', this.maximumColorListener)
      this.maximumColorListener = null
    }
  }
}

customElements.define('x-color-tracking-menu', ColorTrackingMenu)

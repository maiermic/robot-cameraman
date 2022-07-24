import {configurationRequestQueue, getJson} from "./api.js";

const template = document.createElement('template')
template.innerHTML = `
<style>
    .partial-input {
        font-size: 0.8em;
    }
    .angle-limit {
        display: grid;
        grid-template-columns: 9ch 1fr auto 2ch;
        white-space: nowrap;
    }

    input[type="number"] {
        margin: 0.1em;
    }
</style>
<div class="angle-limits">
  <details open class="pan-limit">
      <summary>
          <label>Pan</label>
      </summary>
      <label class="partial-input">
          <span>Active</span>
          <input class="active" type="checkbox">
      </label>
      <label class="partial-input angle-limit">
          <span>Minimum</span>
          <input class="minimum-range"
                 type="range"
                 min="0"
                 max="360"
                 value="0"
                 oninput="this.nextElementSibling.value = this.value">
          <input class="minimum-number"
                 type="number"
                 min="0"
                 max="360"
                 value="0"
                 oninput="this.previousElementSibling.value = this.value">
          <span>°</span>
      </label>
      <label class="partial-input angle-limit">
          <span>Maximum</span>
          <input class="maximum-range"
                 type="range"
                 min="0"
                 max="360"
                 value="0"
                 oninput="this.nextElementSibling.value = this.value">
          <input class="maximum-number"
                 type="number"
                 min="0"
                 max="360"
                 value="0"
                 oninput="this.previousElementSibling.value = this.value">
          <span>°</span>
      </label>
  </details>
  <details open class="tilt-limit">
      <summary>
          <label>Tilt</label>
      </summary>
      <label class="partial-input">
          <span>Active</span>
          <input class="active" type="checkbox">
      </label>
      <label class="partial-input angle-limit">
          <span>Minimum</span>
          <input class="minimum-range"
                 type="range"
                 min="0"
                 max="360"
                 value="0"
                 oninput="this.nextElementSibling.value = this.value">
          <input class="minimum-number"
                 type="number"
                 min="0"
                 max="360"
                 value="0"
                 oninput="this.previousElementSibling.value = this.value">
          <span>°</span>
      </label>
      <label class="partial-input angle-limit">
          <span>Maximum</span>
          <input class="maximum-range"
                 type="range"
                 min="0"
                 max="360"
                 value="0"
                 oninput="this.nextElementSibling.value = this.value">
          <input class="maximum-number"
                 type="number"
                 min="0"
                 max="360"
                 value="0"
                 oninput="this.previousElementSibling.value = this.value">
          <span>°</span>
      </label>
  </details>
</div>
`

class LimitsMenu extends HTMLElement {
  constructor() {
    super().attachShadow({mode: 'open'});
  }

  async connectedCallback() {
    const {
      limits: {
        pan,
        tilt,
      }
    } = await getJson('/api/configuration');
    const node =
      /** @type {DocumentFragment} */
      template.content.cloneNode(true);
    this._panListener = this._setValueAndListener({
      parent: node.querySelector('.pan-limit'),
      value: pan,
      configurationKey: 'pan',
    })
    this._tiltListener = this._setValueAndListener({
      parent: node.querySelector('.tilt-limit'),
      value: tilt,
      configurationKey: 'tilt',
    })
    this.shadowRoot.append(node)
  }

  /**
   * @param parent {Element}
   * @param value {number}
   * @param configurationKey {string}
   * @private
   */
  _setValueAndListener({parent, value, configurationKey}) {
    const [minimum, maximum] = value || [0, 0]
    /** @type {HTMLInputElement} */
    const minimumRangeElement = parent.querySelector('.minimum-range');
    minimumRangeElement.value = String(minimum)
    /** @type {HTMLInputElement} */
    const minimumNumberElement = parent.querySelector('.minimum-number');
    minimumNumberElement.value = String(minimum)
    /** @type {HTMLInputElement} */
    const maximumRangeElement = parent.querySelector('.maximum-range');
    maximumRangeElement.value = String(maximum)
    /** @type {HTMLInputElement} */
    const maximumNumberElement = parent.querySelector('.maximum-number');
    maximumNumberElement.value = String(maximum)
    /** @type {HTMLInputElement} */
    const activeElement = parent.querySelector('.active');
    activeElement.checked = Boolean(value)
    const inputListener = () => {
      // noinspection JSIgnoredPromiseFromCall
      configurationRequestQueue.add({
        limits: {
          [configurationKey]:
            activeElement.checked
              ? [
                Number.parseInt(minimumRangeElement.value),
                Number.parseInt(maximumRangeElement.value),
              ]
              : null,
        }
      });
    };
    parent.addEventListener('input', inputListener)
    return inputListener;
  }

  disconnectedCallback() {
    if (this._panListener) {
      this.shadowRoot.querySelector('.pan-limit')
        .removeEventListener('input', this._panListener)
      this._panListener = null
    }
    if (this._tiltListener) {
      this.shadowRoot.querySelector('.tilt-limit')
        .removeEventListener('input', this._tiltListener)
      this._tiltListener = null
    }
  }
}

customElements.define('x-limits-menu', LimitsMenu)

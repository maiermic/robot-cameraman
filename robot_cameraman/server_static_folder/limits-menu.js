import {configurationRequestQueue, getJson} from "./api.js";
import {range} from "./util.js";

const template = document.createElement('template')
template.innerHTML = `
<style>
    .partial-input {
        font-size: 0.8em;
    }
    .range-limit {
        display: grid;
        grid-template-columns: 9ch 1fr auto 2ch;
        white-space: nowrap;
    }
    .dropdown {
        display: grid;
        grid-template-columns: 9ch 1fr auto;
        white-space: nowrap;
    }

    input[type="number"] {
        margin: 0.1em;
    }
</style>
<div class="angle-limits">
  <label class="partial-input">
      <span>Apply Limits In Manual Mode</span>
      <input class="are-limits-applied-in-manual-mode" type="checkbox">
  </label>
  <details open class="pan-limit">
      <summary>
          <label>Pan</label>
      </summary>
      <label class="partial-input">
          <span>Active</span>
          <input class="active" type="checkbox">
      </label>
      <label class="partial-input range-limit">
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
      <label class="partial-input range-limit">
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
      <label class="partial-input range-limit">
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
      <label class="partial-input range-limit">
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
  <details open class="zoom-limit">
      <summary>
          <label>Zoom Ratio</label>
      </summary>
      <label class="partial-input">
          <span>Active</span>
          <input class="active" type="checkbox">
      </label>
      <label class="partial-input range-limit">
          <span>Minimum</span>
          <input class="minimum-range"
                 type="range"
                 min="1"
                 max="14.3"
                 value="1"
                 step="0.1"
                 oninput="this.nextElementSibling.value = this.value">
          <input class="minimum-number"
                 type="number"
                 min="1"
                 max="14.3"
                 value="1"
                 step="0.1"
                 oninput="this.previousElementSibling.value = this.value">
          <span>x</span>
      </label>
      <label class="partial-input range-limit">
          <span>Maximum</span>
          <input class="maximum-range"
                 type="range"
                 min="1"
                 max="14.3"
                 value="7.1"
                 step="0.1"
                 oninput="this.nextElementSibling.value = this.value">
          <input class="maximum-number"
                 type="number"
                 min="1"
                 max="14.3"
                 value="7.1"
                 step="0.1"
                 oninput="this.previousElementSibling.value = this.value">
          <span>x</span>
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
        areLimitsAppliedInManualMode,
        pan,
        tilt,
        zoom,
        zoomIndex,
      },
      camera: {
        /** @type {{zoom_ratio: number, min_index: number, max_index: number}[]} */
        zoomRatioIndexRanges,
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
    const $zoomLimit = node.querySelector('.zoom-limit');
    if (zoomRatioIndexRanges) {
      $zoomLimit.querySelectorAll('.range-limit').forEach(e => e.remove())
      $zoomLimit.querySelector('summary label').innerText = 'Zoom Index'
      this._zoomListener = this._createZoomIndexLimitDropdown({
        parent: $zoomLimit,
        value: zoomIndex,
        values: zoomRatioIndexRanges
          .flatMap(r =>
            Array.from(range(r.min_index, r.max_index + 1))
              .map(index => ({ratio: r.zoom_ratio, index}))
          ),
        configurationKey: 'zoomIndex',
      })
    } else {
      this._zoomListener = this._setValueAndListener({
        parent: $zoomLimit,
        value: zoom,
        configurationKey: 'zoom',
      })
    }
    /**
     * @param e {InputEvent}
     * @private
     */
    this._areLimitsAppliedInManualModeListener = e => {
      configurationRequestQueue.add({
        limits: {
          areLimitsAppliedInManualMode: e.target.checked,
        }
      })
    }
    /** @type {HTMLInputElement} */
    const areLimitsAppliedInManualModeElement =
      node.querySelector('.are-limits-applied-in-manual-mode');
    areLimitsAppliedInManualModeElement.checked =
      Boolean(areLimitsAppliedInManualMode)
    areLimitsAppliedInManualModeElement
      .addEventListener('input', this._areLimitsAppliedInManualModeListener)
    this.shadowRoot.append(node)
  }

  /**
   * @param parent {Element}
   * @param value {[number, number] | null}
   * @param configurationKey {string}
   * @private
   */
  _setValueAndListener({parent, value, configurationKey}) {
    /** @type {HTMLInputElement} */
    const minimumRangeElement = parent.querySelector('.minimum-range');
    /** @type {HTMLInputElement} */
    const minimumNumberElement = parent.querySelector('.minimum-number');
    /** @type {HTMLInputElement} */
    const maximumRangeElement = parent.querySelector('.maximum-range');
    /** @type {HTMLInputElement} */
    const maximumNumberElement = parent.querySelector('.maximum-number');
    if (value) {
      const [minimum, maximum] = value
      minimumRangeElement.value = String(minimum)
      minimumNumberElement.value = String(minimum)
      maximumRangeElement.value = String(maximum)
      maximumNumberElement.value = String(maximum)
    }
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
                Number.parseFloat(minimumRangeElement.value),
                Number.parseFloat(maximumRangeElement.value),
              ]
              : null,
        }
      });
    };
    parent.addEventListener('input', inputListener)
    return inputListener;
  }

  /**
   * @param parent {Element}
   * @param value {[number, number] | null}
   * @param values {{index: number, ratio: number}[]}
   * @param configurationKey {string}
   * @private
   */
  _createZoomIndexLimitDropdown({parent, value, values, configurationKey}) {
    /**
     * @param labelText {string}
     * @param selected {number}
     * @return {HTMLSelectElement}
     */
    const createDropdown = ({labelText, selected}) => {
      const $label = document.createElement('label');
      $label.classList.add('partial-input', 'dropdown')
      const $title = document.createElement('span');
      $title.innerText = labelText
      $label.appendChild($title)
      const $select = document.createElement('select');
      for (const {index, ratio} of values) {
        const $option = document.createElement('option');
        $option.value = String(index)
        $option.innerText = `${index} (${ratio.toFixed(1)}x)`
        if (index === selected) {
          $option.selected = true
        }
        $select.appendChild($option)
      }
      $label.appendChild($select)
      parent.appendChild($label)
      return $select
    }
    const $minimum = createDropdown({
      labelText: 'Minimum',
      selected: value ? value.at(0) : values.at(0).index
    })
    const $maximum = createDropdown({
      labelText: 'Maximum',
      selected: value ? value.at(-1) : values.at(-1).index
    })
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
                Number.parseInt($minimum.value),
                Number.parseInt($maximum.value),
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
    if (this._areLimitsAppliedInManualModeListener) {
      this.shadowRoot.querySelector('.are-limits-applied-in-manual-mode')
        .removeEventListener('input', this._areLimitsAppliedInManualModeListener)
      this._areLimitsAppliedInManualModeListener = null
    }
    // TODO remove this._zoomListener
  }
}

customElements.define('x-limits-menu', LimitsMenu)

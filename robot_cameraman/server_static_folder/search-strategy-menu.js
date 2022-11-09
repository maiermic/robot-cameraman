import {configurationRequestQueue, getJson} from "./api.js";
import {range} from "./util.js";

const template = document.createElement('template')
template.innerHTML = `
<style>
    .partial-input {
        font-size: 0.8em;
    }
    .numbered-range-input {
        display: grid;
        grid-template-columns: 4ch 1fr auto 1ch;
        white-space: nowrap;
    }
    .dropdown {
        display: grid;
        grid-template-columns: 11ch 1fr;
        white-space: nowrap;
    }

    input[type="number"] {
        margin: 0.1em;
    }
</style>
<div>
  <label class="partial-input">
      <span>Zoom while rotating</span>
      <input class="is-zoom-while-rotating" type="checkbox">
  </label>
  <label class="partial-input numbered-range-input pan-target">
      <span>Pan</span>
      <input class="range"
             type="range"
             min="0"
             max="360"
             value="0"
             oninput="this.nextElementSibling.value = this.value">
      <input class="number"
             type="number"
             min="0"
             max="360"
             value="0"
             oninput="this.previousElementSibling.value = this.value">
      <span>°</span>
  </label>
  <label class="partial-input numbered-range-input tilt-target">
      <span>Tilt</span>
      <input class="range"
             type="range"
             min="0"
             max="360"
             value="0"
             oninput="this.nextElementSibling.value = this.value">
      <input class="number"
             type="number"
             min="0"
             max="360"
             value="0"
             oninput="this.previousElementSibling.value = this.value">
      <span>°</span>
  </label>
  <label class="partial-input numbered-range-input zoom-target">
      <span>Zoom Ratio</span>
      <input class="range"
             type="range"
             min="1"
             max="14.3"
             value="1"
             step="0.1"
             oninput="this.nextElementSibling.value = this.value">
      <input class="number"
             type="number"
             min="1"
             max="14.3"
             value="1"
             step="0.1"
             oninput="this.previousElementSibling.value = this.value">
      <span>x</span>
  </label>
</div>
`

class SearchStrategyMenu extends HTMLElement {
  constructor() {
    super().attachShadow({mode: 'open'});
  }

  async connectedCallback() {
    const {
      searchTarget: {
        isZoomWhileRotating,
        pan,
        tilt,
        zoomRatio,
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
      parent: node.querySelector('.pan-target'),
      value: pan,
      configurationKey: 'pan',
    })
    this._tiltListener = this._setValueAndListener({
      parent: node.querySelector('.tilt-target'),
      value: tilt,
      configurationKey: 'tilt',
    })
    const $zoomTarget = node.querySelector('.zoom-target');
    if (zoomRatioIndexRanges) {
      this._zoomListener = this._createZoomIndexLimitDropdown({
        parent: $zoomTarget,
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
        parent: $zoomTarget,
        value: zoomRatio,
        configurationKey: 'zoomRatio',
      })
    }
    /**
     * @param e {InputEvent}
     * @private
     */
    this._isZoomWhileRotatingListener = e => {
      configurationRequestQueue.add({
        searchTarget: {
          isZoomWhileRotating: e.target.checked,
        }
      })
    }
    /** @type {HTMLInputElement} */
    const isZoomWhileRotatingElement =
      node.querySelector('.is-zoom-while-rotating');
    isZoomWhileRotatingElement.checked =
      Boolean(isZoomWhileRotating)
    isZoomWhileRotatingElement
      .addEventListener('input', this._isZoomWhileRotatingListener)
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
    const rangeElement = parent.querySelector('.range');
    /** @type {HTMLInputElement} */
    const numberElement = parent.querySelector('.number');
    if (value) {
      rangeElement.value = String(value)
      numberElement.value = String(value)
    }
    const inputListener = () => {
      // noinspection JSIgnoredPromiseFromCall
      configurationRequestQueue.add({
        searchTarget: {
          [configurationKey]: Number.parseFloat(rangeElement.value),
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
    const selected = value || values.at(0).index
    const $label = document.createElement('label');
    $label.classList.add('partial-input', 'dropdown', 'zoom-target')
    const $title = document.createElement('span');
    $title.innerText = 'Zoom Index'
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
    parent.replaceWith($label)
    const inputListener = () => {
      // noinspection JSIgnoredPromiseFromCall
      configurationRequestQueue.add({
        searchTarget: {
          [configurationKey]: Number.parseInt($select.value),
        }
      });
    };
    $label.addEventListener('input', inputListener)
    return inputListener;
  }

  disconnectedCallback() {
    if (this._panListener) {
      this.shadowRoot.querySelector('.pan-target')
        .removeEventListener('input', this._panListener)
      this._panListener = null
    }
    if (this._tiltListener) {
      this.shadowRoot.querySelector('.tilt-target')
        .removeEventListener('input', this._tiltListener)
      this._tiltListener = null
    }
    if (this._isZoomWhileRotatingListener) {
      this.shadowRoot.querySelector('.is-zoom-while-rotating')
        .removeEventListener('input', this._isZoomWhileRotatingListener)
      this._isZoomWhileRotatingListener = null
    }
    // TODO remove this._zoomListener
  }
}

customElements.define('x-search-strategy-menu', SearchStrategyMenu)

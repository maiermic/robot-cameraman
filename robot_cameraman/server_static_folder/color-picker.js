import {hsvToRgbHex, rgbHexToHsv} from "./color.js";

const template = document.createElement('template')
template.innerHTML = `
<style>
    .color-tracking-menu__color-picker__partial-input {
        display: grid;
        grid-template-columns: 2ch 1fr auto 2ch;
        font-size: 0.8em;
        white-space: nowrap;
    }

    input[type="number"] {
        margin: 0.1em;
    }
</style>
<details open class="color-tracking-menu__color-picker">
    <summary>
        <label>
            <slot name="title">TITLE</slot>
            <input id="color" type="color" value="#FFFFFF">
        </label>
    </summary>
    <label class="color-tracking-menu__color-picker__partial-input">
        <span>H</span>
        <input id="hue-range"
               type="range"
               min="0"
               max="360"
               value="0"
               oninput="this.nextElementSibling.value = this.value">
        <input id="hue-number"
               type="number"
               min="0"
               max="360"
               value="0"
               oninput="this.previousElementSibling.value = this.value">
        <span>°</span>
    </label>
    <label class="color-tracking-menu__color-picker__partial-input">
        <span>S</span>
        <input id="saturation-range"
               type="range"
               min="0"
               max="100"
               value="0"
               oninput="this.nextElementSibling.value = this.value">
        <input id="saturation-number"
               type="number"
               min="0"
               max="100"
               value="0"
               oninput="this.previousElementSibling.value = this.value">
        <span>%</span>
    </label>
    <label class="color-tracking-menu__color-picker__partial-input">
        <span>V</span>
        <input id="value-range"
               type="range"
               min="0"
               max="100"
               value="0"
               oninput="this.nextElementSibling.value = this.value">
        <input id="value-number"
               type="number"
               min="0"
               max="100"
               value="0"
               oninput="this.previousElementSibling.value = this.value">
        <span>%</span>
    </label>
</details>
`


class ColorPicker extends HTMLElement {
  constructor() {
    super()
      .attachShadow({mode: 'open'})
      .append(template.content.cloneNode(true));
  }

  static get observedAttributes() {
    return ['color'];
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (name === 'color') {
      this.color = newValue
    }
  }

  connectedCallback() {
    this._colorElement.addEventListener('input', this.onInputColor)
    this._hueRangeElement.addEventListener('input', this.onInputHue)
    this._hueNumberElement.addEventListener('input', this.onInputHue)
    this._saturationRangeElement
      .addEventListener('input', this.onInputSaturation)
    this._saturationNumberElement
      .addEventListener('input', this.onInputSaturation)
    this._valueRangeElement.addEventListener('input', this.onInputValue)
    this._valueNumberElement.addEventListener('input', this.onInputValue)
  }

  disconnectedCallback() {
    this._colorElement.removeEventListener('input', this.onInputColor)
    this._hueRangeElement.removeEventListener('input', this.onInputHue)
    this._hueNumberElement.removeEventListener('input', this.onInputHue)
    this._saturationRangeElement
      .removeEventListener('input', this.onInputSaturation)
    this._saturationNumberElement
      .removeEventListener('input', this.onInputSaturation)
    this._valueRangeElement.removeEventListener('input', this.onInputValue)
    this._valueNumberElement.removeEventListener('input', this.onInputValue)
  }

  onInputColor = () => {
    this.color = rgbHexToHsv(this._colorElement.value)
  }

  /**
   * @param event {InputEvent}
   */
  onInputHue = (event) => {
    this.color = {
      h: event.target.value,
      s: this.saturation,
      v: this.value,
    }
  }

  /**
   * @param event {InputEvent}
   */
  onInputSaturation = (event) => {
    this.color = {
      h: this.hue,
      s: event.target.value,
      v: this.value,
    }
  }

  /**
   * @param event {InputEvent}
   */
  onInputValue = (event) => {
    this.color = {
      h: this.hue,
      s: this.saturation,
      v: event.target.value,
    }
  }

  /**
   * @returns {HTMLInputElement}
   * @private
   */
  get _colorElement() {
    return this.shadowRoot.getElementById('color')
  }

  /**
   * @returns {HTMLInputElement}
   * @private
   */
  get _hueRangeElement() {
    return this.shadowRoot.getElementById('hue-range')
  }

  /**
   * @returns {HTMLInputElement}
   * @private
   */
  get _hueNumberElement() {
    return this.shadowRoot.getElementById('hue-number')
  }

  /**
   * @returns {HTMLInputElement}
   * @private
   */
  get _saturationRangeElement() {
    return this.shadowRoot.getElementById('saturation-range')
  }

  /**
   * @returns {HTMLInputElement}
   * @private
   */
  get _saturationNumberElement() {
    return this.shadowRoot.getElementById('saturation-number')
  }

  /**
   * @returns {HTMLInputElement}
   * @private
   */
  get _valueRangeElement() {
    return this.shadowRoot.getElementById('value-range')
  }

  /**
   * @returns {HTMLInputElement}
   * @private
   */
  get _valueNumberElement() {
    return this.shadowRoot.getElementById('value-number')
  }

  set color(value) {
    const {h, s, v} = typeof value === 'string' ? JSON.parse(value) : value;
    this._colorElement.value = hsvToRgbHex(h, s, v)
    this.hue = h
    this.saturation = s
    this.value = v
  }

  get color() {
    return {
      h: this.hue,
      s: this.saturation,
      v: this.value,
    }
  }

  set hue(value) {
    value = Math.round(value)
    this._hueRangeElement.value = value
    this._hueNumberElement.value = value
  }

  get hue() {
    return Number.parseInt(this._hueRangeElement.value)
  }

  set saturation(value) {
    value = Math.round(value)
    this._saturationRangeElement.value = value
    this._saturationNumberElement.value = value
  }

  get saturation() {
    return Number.parseInt(this._saturationRangeElement.value)
  }

  set value(value) {
    value = Math.round(value)
    this._valueRangeElement.value = value
    this._valueNumberElement.value = value
  }

  get value() {
    return Number.parseInt(this._valueRangeElement.value)
  }

}

customElements.define('x-color-picker', ColorPicker)

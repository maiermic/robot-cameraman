import {assignDeep, isObject} from "./assign-deep.js";

export function getJson(url) {
  return fetch(url, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  }).then(r => r.json());
}

export function putJson(url, data) {
  return fetch(url, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data)
  });
}

/**
 * Do one PUT request at a time.
 * If payload is added to the queue and no request is in progress,
 * the request is done immediately with the provided payload.
 * If a request is running, the passed payload is merged with the previously
 * added payload that has not been sent yet.
 * When the request finishes, another request is send with the merged payload,
 * that has been gathered in the meantime.
 */
class RequestQueue {
  constructor(url) {
    this._url = url;
    this._payload = null;
    this._isSending = false;
  }

  add(payload) {
    if (this._isSending) {
      if (this._payload) {
        this._payload = this._merge(this._payload, payload)
      } else {
        this._payload = payload
      }
    } else {
      this._send(payload);
    }
  }

  _merge(current, next) {
    if (typeof current !== typeof next) {
      throw Error(
        `Merge expects same type: current = ${current}, next = ${next}`)
    }
    if (isObject(next)) {
      return assignDeep(current, next)
    }
    return next
  }

  _send(payload) {
    this._isSending = true;
    putJson(this._url, payload)
      .then(_ => {
        if (this._payload) {
          const nextPayload = this._payload;
          this._payload = null;
          this._send(nextPayload)
        } else {
          this._isSending = false;
        }
      })
  }
}

export const configurationRequestQueue = new RequestQueue('api/configuration')

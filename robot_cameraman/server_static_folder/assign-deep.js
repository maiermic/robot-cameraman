// Modified version of https://github.com/jonschlinkert/mixin-deep/blob/8f464c8ce9761a8c9c2b3457eaeee9d404fa7af9/index.js

export const isObject = val => {
  return typeof val === 'function' || (typeof val === 'object' && val !== null && !Array.isArray(val));
};

const isValidKey = key => {
  return key !== '__proto__' && key !== 'constructor' && key !== 'prototype';
};

export const assignDeep = (target, ...rest) => {
  for (let obj of rest) {
    if (isObject(obj)) {
      for (let key in obj) {
        if (isValidKey(key)) {
          assign(target, obj[key], key);
        }
      }
    }
  }
  return target;
};

function assign(target, val, key) {
  let obj = target[key];
  if (isObject(val) && isObject(obj)) {
    assignDeep(obj, val);
  } else if (isObject(val)) {
    target[key] = assignDeep({}, val);
  } else {
    target[key] = val;
  }
}

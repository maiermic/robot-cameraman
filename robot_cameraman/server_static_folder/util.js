/**
 *
 * @param start {number} inclusive
 * @param stop {number} exclusive
 * @param step {number} default is 1
 * @generator
 * @yields {number}
 */
export function* range(start, stop, step = 1) {
  for (let i = start; i < stop; i += step) {
    yield i;
  }
}

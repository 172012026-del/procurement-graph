/** Follow the active native tab without taking over its keyboard or click behavior. */
const handles = new WeakMap()

export const tabIndicator = {
  mounted(element) {
    let frame = 0, disposed = false
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)')
    function update(reveal = false) {
      if (disposed) return
      const active = element.querySelector(':scope > .active')
      if (!active) { element.style.setProperty('--tab-width', '0px'); return }
      const parent = element.getBoundingClientRect(), box = active.getBoundingClientRect()
      element.style.setProperty('--tab-left', `${box.left - parent.left + element.scrollLeft}px`)
      element.style.setProperty('--tab-top', `${box.top - parent.top + element.scrollTop}px`)
      element.style.setProperty('--tab-width', `${box.width}px`)
      element.style.setProperty('--tab-height', `${box.height}px`)
      if (reveal && element.scrollWidth > element.clientWidth) {
        const left = box.left - parent.left + element.scrollLeft
        const next = left < element.scrollLeft + 12 ? left - 12
          : left + box.width > element.scrollLeft + element.clientWidth - 12 ? left + box.width - element.clientWidth + 12 : element.scrollLeft
        if (next !== element.scrollLeft) element.scrollTo({ left: Math.max(0, next), behavior: reduced.matches ? 'auto' : 'smooth' })
      }
    }
    function schedule(reveal = false) { cancelAnimationFrame(frame); frame = requestAnimationFrame(() => update(reveal)) }
    element.classList.add('tracked-tabs')
    const size = new ResizeObserver(() => schedule())
    size.observe(element)
    for (const child of element.children) size.observe(child)
    const active = new MutationObserver(() => schedule(true))
    active.observe(element, { attributes: true, subtree: true, attributeFilter: ['class', 'aria-pressed', 'aria-current'], childList: true })
    update()
    document.fonts?.ready.then(() => schedule())
    handles.set(element, () => { disposed = true; cancelAnimationFrame(frame); size.disconnect(); active.disconnect() })
  },
  beforeUnmount(element) { handles.get(element)?.(); handles.delete(element) }
}

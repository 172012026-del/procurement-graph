import { onBeforeUnmount, onMounted, ref } from 'vue'

export function useInterfacePolish() {
  const scrolled = ref(false), showBackToTop = ref(false)
  let frame = 0
  function update() {
    frame = 0
    scrolled.value = window.scrollY > 12
    showBackToTop.value = window.scrollY > 580
  }
  function schedule() { if (!frame) frame = requestAnimationFrame(update) }
  function backToTop() {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    window.scrollTo({ top: 0, behavior: reduced ? 'instant' : 'smooth' })
  }
  onMounted(() => { update(); window.addEventListener('scroll', schedule, { passive: true }); window.addEventListener('resize', schedule) })
  onBeforeUnmount(() => { cancelAnimationFrame(frame); window.removeEventListener('scroll', schedule); window.removeEventListener('resize', schedule) })
  return { scrolled, showBackToTop, backToTop }
}

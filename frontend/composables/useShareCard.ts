/**
 * Share card generation.
 * Mobile: navigator.share URL (synchronous, preserves user gesture).
 * Desktop: html2canvas PNG download.
 */

export function useShareCard() {
  const generating = ref(false)

  async function shareUrl(title: string, url: string): Promise<void> {
    if (navigator.share) {
      try {
        await navigator.share({ title, url })
        return
      } catch {
        // User cancelled — do nothing
        return
      }
    }
    // Desktop fallback: copy URL to clipboard
    try {
      await navigator.clipboard.writeText(url)
    } catch { /* ignore */ }
  }

  async function captureElement(el: HTMLElement, filename: string): Promise<void> {
    if (!el) return
    generating.value = true
    try {
      const { default: html2canvas } = await import('html2canvas')
      const canvas = await html2canvas(el, {
        backgroundColor: '#0a0d14',
        scale: 2,
        useCORS: false,
        allowTaint: true,
        logging: false,
        // Ignore external resources that cause taint
        ignoreElements: (node) => node.tagName === 'IMG' && !(node as HTMLImageElement).src.startsWith('data:'),
      })

      canvas.toBlob((blob) => {
        if (!blob) return
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.download = `${filename}.png`
        link.href = url
        link.click()
        setTimeout(() => URL.revokeObjectURL(url), 5000)
      }, 'image/png')
    } catch (e) {
      console.warn('Share card generation failed:', e)
    } finally {
      generating.value = false
    }
  }

  return { captureElement, shareUrl, generating }
}

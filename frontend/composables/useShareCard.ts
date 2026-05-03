/**
 * Client-only html2canvas wrapper for branded share card generation.
 * Always lazy-loads html2canvas to avoid SSR issues.
 */

export function useShareCard() {
  const generating = ref(false)

  async function captureElement(el: HTMLElement, filename: string): Promise<void> {
    if (!el) return
    generating.value = true
    try {
      const { default: html2canvas } = await import('html2canvas')
      const canvas = await html2canvas(el, {
        backgroundColor: '#0a0d14',
        scale: 2,
        useCORS: true,
        allowTaint: false,
        logging: false,
      })

      if (navigator.share && navigator.canShare) {
        canvas.toBlob(async (blob) => {
          if (!blob) return
          const file = new File([blob], `${filename}.png`, { type: 'image/png' })
          try {
            await navigator.share({ files: [file], title: filename })
          } catch {
            // User cancelled or not supported — fall back to download
            _download(canvas, filename)
          }
        }, 'image/png')
      } else {
        _download(canvas, filename)
      }
    } finally {
      generating.value = false
    }
  }

  function _download(canvas: HTMLCanvasElement, filename: string) {
    const link = document.createElement('a')
    link.download = `${filename}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
  }

  return { captureElement, generating }
}

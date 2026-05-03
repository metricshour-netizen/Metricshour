/**
 * Share card using pre-generated R2 OG images.
 * No html2canvas — avoids all async user-gesture and canvas-taint problems.
 *
 * Mobile:  navigator.share({ url }) — synchronous, preserves user gesture
 * Desktop: fetch OG PNG from CDN → blob URL → link.click() download
 *          (downloads don't trigger popup blockers, so async is fine on desktop)
 */

export function useShareCard() {
  const downloading = ref(false)

  /** Mobile — share current page URL via native share sheet. */
  async function sharePage(title: string): Promise<void> {
    if (!navigator.share) return
    try {
      await navigator.share({ title, url: window.location.href })
    } catch {
      // user cancelled — do nothing
    }
  }

  /** Desktop — download the server-generated OG PNG from R2. */
  async function downloadOgImage(imageUrl: string, filename: string): Promise<void> {
    downloading.value = true
    try {
      const res = await fetch(imageUrl)
      if (!res.ok) throw new Error(`fetch failed: ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${filename}.png`
      a.click()
      setTimeout(() => URL.revokeObjectURL(url), 5000)
    } catch (e) {
      // Fallback: open image in new tab so user can right-click → Save
      window.open(imageUrl, '_blank', 'noopener')
    } finally {
      downloading.value = false
    }
  }

  return { sharePage, downloadOgImage, downloading }
}

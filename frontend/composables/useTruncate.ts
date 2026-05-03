/**
 * Sentence-aware text truncation.
 * Prevents mid-sentence cuts in meta descriptions, insight cards, and summaries.
 */

export function useTruncate() {
  /**
   * Truncate at the last sentence boundary at or before maxLen.
   * Falls back to word boundary if no sentence break found within tolerance.
   */
  function truncateAtSentence(text: string, maxLen: number): string {
    if (!text || text.length <= maxLen) return text ?? ''

    const slice = text.slice(0, maxLen + 1)
    // Find last sentence-ending punctuation (.!?) followed by space or end
    const sentenceEnd = slice.search(/[.!?][^.!?]*$/)
    if (sentenceEnd > maxLen * 0.5) {
      // Found a sentence break in the second half — use it
      const cut = slice.slice(0, sentenceEnd + 1).trimEnd()
      return cut
    }

    // Fallback: word boundary
    return truncateAtWord(text, maxLen)
  }

  /**
   * Truncate at the last word boundary at or before maxLen, appending '…'.
   */
  function truncateAtWord(text: string, maxLen: number): string {
    if (!text || text.length <= maxLen) return text ?? ''
    const slice = text.slice(0, maxLen)
    const lastSpace = slice.lastIndexOf(' ')
    if (lastSpace > maxLen * 0.6) {
      return slice.slice(0, lastSpace).trimEnd() + '…'
    }
    return slice.trimEnd() + '…'
  }

  return { truncateAtSentence, truncateAtWord }
}

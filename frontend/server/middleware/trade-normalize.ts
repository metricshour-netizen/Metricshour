/**
 * Normalises malformed trade URLs to canonical iso2-iso2 format.
 *
 * Root cause: trade/[pair].vue splits the pair slug on "-" which incorrectly
 * handles multi-word country names (e.g. "gd-united-kingdom" → codeB="kingdom").
 * The trade API accepts both ISO2 codes AND country slugs, so canonical pairs exist,
 * but the Nuxt page parser never reaches the API correctly.
 *
 * Patterns handled:
 *   {iso2}-{country-slug}        e.g. gd-united-kingdom  → gd-gb
 *   {iso2}--{country-slug}       e.g. nz--united-kingdom → nz-gb
 *   {country-slug}--{iso2}       reverse of above
 *   {country-slug}--{country-slug} e.g. singapore--china → sg-cn
 *   {country-slug}-{country-slug}  e.g. mexico-united-states → mx-us
 */

const SLUG_TO_ISO2: Record<string, string> = {
  // Major economies
  'united-states': 'us', 'united-kingdom': 'gb', 'china': 'cn',
  'germany': 'de', 'france': 'fr', 'japan': 'jp', 'south-korea': 'kr',
  'hong-kong': 'hk', 'singapore': 'sg', 'australia': 'au', 'canada': 'ca',
  'india': 'in', 'brazil': 'br', 'mexico': 'mx', 'italy': 'it',
  'spain': 'es', 'netherlands': 'nl', 'switzerland': 'ch', 'austria': 'at',
  'sweden': 'se', 'norway': 'no', 'denmark': 'dk', 'finland': 'fi',
  'poland': 'pl', 'portugal': 'pt', 'greece': 'gr', 'turkey': 'tr',
  'russia': 'ru', 'indonesia': 'id', 'vietnam': 'vn', 'thailand': 'th',
  'malaysia': 'my', 'philippines': 'ph', 'taiwan': 'tw',
  // Middle East + Africa
  'united-arab-emirates': 'ae', 'saudi-arabia': 'sa', 'qatar': 'qa',
  'bahrain': 'bh', 'kuwait': 'kw', 'israel': 'il', 'egypt': 'eg',
  'south-africa': 'za', 'nigeria': 'ng', 'ethiopia': 'et', 'kenya': 'ke',
  'ghana': 'gh', 'tanzania': 'tz', 'morocco': 'ma', 'algeria': 'dz',
  'senegal': 'sn', 'cameroon': 'cm', 'zimbabwe': 'zw', 'zambia': 'zm',
  'namibia': 'na', 'botswana': 'bw', 'malawi': 'mw',
  'mauritania': 'mr', 'mali': 'ml', 'benin': 'bj', 'togo': 'tg',
  'liberia': 'lr', 'sierra-leone': 'sl', 'guinea': 'gn',
  'cape-verde': 'cv', 'sao-tome-and-principe': 'st', 'comoros': 'km',
  'seychelles': 'sc', 'djibouti': 'dj', 'eritrea': 'er',
  // Americas
  'argentina': 'ar', 'colombia': 'co', 'chile': 'cl', 'peru': 'pe',
  'venezuela': 've', 'ecuador': 'ec', 'bolivia': 'bo', 'paraguay': 'py',
  'uruguay': 'uy', 'guyana': 'gy', 'suriname': 'sr',
  'trinidad-and-tobago': 'tt', 'panama': 'pa', 'costa-rica': 'cr',
  'guatemala': 'gt', 'honduras': 'hn', 'el-salvador': 'sv',
  'nicaragua': 'ni', 'cuba': 'cu', 'haiti': 'ht', 'jamaica': 'jm',
  'bahamas': 'bs', 'barbados': 'bb', 'grenada': 'gd',
  'antigua-and-barbuda': 'ag', 'saint-kitts-and-nevis': 'kn',
  'saint-vincent-and-the-grenadines': 'vc', 'saint-lucia': 'lc',
  'dominica': 'dm', 'belize': 'bz', 'bermuda': 'bm',
  'cayman-islands': 'ky', 'turks-and-caicos-islands': 'tc',
  'sint-maarten': 'sx', 'aruba': 'aw', 'curacao': 'cw',
  // Europe (non-EU/EEA)
  'ukraine': 'ua', 'belarus': 'by', 'moldova': 'md', 'georgia': 'ge',
  'armenia': 'am', 'azerbaijan': 'az', 'kazakhstan': 'kz',
  'north-macedonia': 'mk', 'albania': 'al', 'serbia': 'rs',
  'montenegro': 'me', 'kosovo': 'xk', 'croatia': 'hr',
  'bosnia-and-herzegovina': 'ba', 'slovenia': 'si', 'slovakia': 'sk',
  'czech-republic': 'cz', 'hungary': 'hu', 'romania': 'ro',
  'bulgaria': 'bg', 'estonia': 'ee', 'latvia': 'lv', 'lithuania': 'lt',
  'luxembourg': 'lu', 'malta': 'mt', 'cyprus': 'cy', 'iceland': 'is',
  'liechtenstein': 'li', 'andorra': 'ad', 'san-marino': 'sm',
  'monaco': 'mc',
  // Asia-Pacific
  'new-zealand': 'nz', 'pakistan': 'pk', 'bangladesh': 'bd',
  'sri-lanka': 'lk', 'nepal': 'np', 'myanmar': 'mm', 'cambodia': 'kh',
  'laos': 'la', 'bhutan': 'bt', 'maldives': 'mv',
  'mongolia': 'mn', 'uzbekistan': 'uz', 'kyrgyzstan': 'kg',
  'tajikistan': 'tj', 'turkmenistan': 'tm', 'afghanistan': 'af',
  'iran': 'ir', 'iraq': 'iq', 'syria': 'sy', 'jordan': 'jo',
  'lebanon': 'lb', 'oman': 'om', 'yemen': 'ye',
  'north-korea': 'kp', 'brunei': 'bn',
  'kiribati': 'ki', 'samoa': 'ws', 'tonga': 'to',
  'fiji': 'fj', 'vanuatu': 'vu', 'solomon-islands': 'sb',
  'papua-new-guinea': 'pg', 'timor-leste': 'tl',
  // Additional slugs seen in GSC data
  'austria': 'at',  // also used in double-dash pairs
  'tanzania-united-arab-emirates': '',  // will be handled as full-slug pair
}

// Returns ISO2 if slug maps to one, otherwise returns original
function resolveCode(part: string): string {
  const lower = part.toLowerCase()
  // Already ISO2 (2 letters)
  if (/^[a-z]{2}$/.test(lower)) return lower
  return SLUG_TO_ISO2[lower] ?? lower
}

export default defineEventHandler((event) => {
  const url = event.node.req.url
  if (!url?.startsWith('/trade/')) return

  const [rawPath] = url.split('?')
  // Strip leading /trade/ and trailing /
  const pair = rawPath.slice(7).replace(/\/$/, '')

  // Skip the index page and non-pair paths
  if (!pair || pair.includes('/')) return

  let partA: string
  let partB: string

  if (pair.includes('--')) {
    // Already using double-dash separator (e.g. nz--united-kingdom)
    const segs = pair.split('--')
    partA = segs[0]
    partB = segs[segs.length - 1]
  } else {
    // Single-dash: either iso2-slug or slug-slug
    const dashIdx = pair.indexOf('-')
    if (dashIdx < 0) return

    const firstSeg = pair.slice(0, dashIdx)
    const rest = pair.slice(dashIdx + 1)

    if (firstSeg.length === 2 && /^[a-z]{2}$/.test(firstSeg)) {
      // Pattern: iso2-{rest} where rest may be multi-word country slug
      partA = firstSeg
      partB = rest
    } else {
      // Pattern: fullslug-fullslug — try resolving both parts
      // This is ambiguous for multi-word names; only handle known exact matches
      const fullResolved = SLUG_TO_ISO2[pair]
      if (fullResolved) return // skip — let page handle
      partA = firstSeg
      partB = rest
    }
  }

  const isoA = resolveCode(partA)
  const isoB = resolveCode(partB)

  // Only redirect if we actually resolved something to ISO2
  if (isoA === partA && isoB === partB) return
  if (!/^[a-z]{2}$/.test(isoA) || !/^[a-z]{2}$/.test(isoB)) return

  const canonical = `/trade/${isoA}-${isoB}/`
  if (canonical === rawPath || canonical === rawPath + '/') return

  return sendRedirect(event, canonical, 301)
})

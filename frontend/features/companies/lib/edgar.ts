/** The company's filing index on SEC EDGAR, every form: the lead's "Company on SEC EDGAR" link and
 *  the page's JSON-LD `sameAs`. */
export const edgarCompanyUrl = (cik: string) => `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${cik}`

/** A CIK as EDGAR prints it, ten digits with leading zeros ("0000320193"); the API may store it bare. */
export const displayCik = (cik: string) => (/^\d{1,10}$/.test(cik) ? cik.padStart(10, '0') : cik)

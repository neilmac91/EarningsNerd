/**
 * A reader's address set in a sentence, breaking after its @ before anywhere else, as AuthShell's support address
 * does (chief design on #1750): under 200% text "unverified@" over "example.com", where the caller's `break-words`
 * alone ended it on a fragment ("unverified@example.co" over "m"). `break-words` still breaks a part longer than the
 * line. The <wbr> is a break opportunity only, so the address reads and copies whole.
 */
export default function AddressText({ address }: { address: string }) {
  const at = address.lastIndexOf('@')
  if (at < 0) return <>{address}</>
  return (
    <>
      {address.slice(0, at + 1)}
      <wbr />
      {address.slice(at + 1)}
    </>
  )
}

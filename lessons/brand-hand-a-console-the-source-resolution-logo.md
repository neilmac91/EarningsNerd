# Hand a console the full-resolution logo; never shrink a brand raster to its recommended size

Date: 2026-10-17   Area: brand, ops

**Context**: For F38, the Google sign-in screen, Google's help page for the Branding fields
(support.google.com/cloud/answer/15549049) asks for a JPG, PNG or BMP of at most 1 MB and says
"Image should be square and 120px by 120px for the best display results". A new name or logo shows
only once the app is verified. The founder supplied the app tile as a full-bleed 1024×1024 PNG of
20 KB, its ground and mark the brand tokens `#4F7A63` and `#F4F3EE`. The session resized it to
120×120 with Lanczos and sent that copy as the file to upload. The founder found it "extremely
blurry": "I don't want this poor quality to be reflective of EarningsNerd." The original met every
stated requirement all along.

**Rule**: When a console, store or provider takes a raster of the mark or the app tile (Google's
consent screen, Stripe's branding, an app store), hand over the highest-resolution source PNG that
its stated limits allow. A recommended pixel size describes how the service displays the image; it
is not a reason to downsample the file you hand over. Never resize, recompress or convert a brand
asset for the founder unless the service rejects the source; then make the smallest change it
requires, from the source and never from an earlier copy. Judge a brand raster you hand over at the
size the founder will view it, on a phone too. A brief that asks another agent to upload a brand
asset says the same: upload the file as attached, and stop rather than make another version.

**Evidence**: PR #1383, which records the correction; `tasks/todo.md` F38 (the Google and Apple
consent screens) and F34 (Stripe's branding) link here. The founder's 1024×1024 tile is not tracked.
The tracked vector tile, a rounded tile on a transparent ground in the same two tokens, is
`frontend/public/assets/earningsnerd-appicon.svg`, from which a PNG of any size can be rendered.
For the mark itself, see `lessons/brand-the-mark-is-protected.md`.

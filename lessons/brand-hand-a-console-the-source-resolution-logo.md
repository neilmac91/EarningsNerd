# Hand a console the full-resolution logo; never shrink a brand raster to its recommended size

Date: 2026-10-17   Area: brand, ops

**Context**: For F38, the Google sign-in screen, Google's Branding page asks for a square logo of
120 by 120 pixels "for the best results" and accepts a JPG, PNG or BMP of up to 1 MB. The founder
supplied the app tile as a 1024×1024 PNG of 20 KB, whose ground and mark match the brand tokens
(`#4F7A63` and a cream `#F4F3EE`). The session resized it to 120×120 with Lanczos and sent that copy
as the file to upload. On the founder's phone, which showed it at the screen's width, it read as
"extremely blurry": "I don't want this poor quality to be reflective of EarningsNerd." The original
was inside Google's limit all along, and Google scales an upload itself.

**Rule**: When a console, store or provider takes a raster of the mark or the app tile (Google's
consent screen, Stripe's branding, an app store), hand over the highest-resolution source PNG that
its stated limits allow, and let the service scale it. A recommended pixel size is a hint, not a
reason to downsample. Never resize, recompress or convert a brand asset for the founder unless the
service rejects the source; then make the smallest change it requires, from the source and never
from an earlier copy. Judge a brand raster you hand over at the size it will be viewed, including a
phone that enlarges it. A brief that asks another agent to upload a brand asset says the same:
upload the file as attached, and stop rather than make another version.

**Evidence**: PR #1383, which records the correction; `tasks/todo.md` F38 (the Google and Apple
consent screens) and F34 (Stripe's branding), which take the same source file; the mark itself is
`lessons/brand-the-mark-is-protected.md`.

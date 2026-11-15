# Screen-photo simulation

Run `python -m eval.screen --samples 5`. This renders a text PDF with temporary 10% mark opacity, places it inside gray screen margins and a dark bezel, applies mild perspective, 1-pixel Gaussian blur, fine neutral screen texture, independent channel noise and JPEG quality85. Conditions vary neutral/blue/warm gains, increased exposure and80% resizing. The simulation changes neither the application's opacity setting nor encoder defaults.

The recorded run recovered25/25 test IDs across5 conditions and rejected5/5 unmarked controls. These conditions already passed with the existing page-registration fallback; they do not reproduce the user's missing physical photo. `tests/test_screen.py` additionally checks45° screen rotation and verifies safe rejection when channel clipping makes faint marks on a blank page identical to its background.

This is a controlled regression harness, not proof of success with a particular camera, screen, brightness, moiré pattern or exposure. No real camera sample was available in the attachment directory. Phone-image capture is still needed to test the reported failure directly.

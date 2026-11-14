# Prototype physical language

A 32-bit recipient ID is encoded as four big-endian bytes followed by eight Reed–Solomon parity bytes. The resulting 96 bits are repeated four times and distributed over 384 positions in a deterministic shuffled 24 × 16 grid on an A4 page. Each position encodes one bit as a single grey dot placed to the left or right of the cell centre. A decoder rectifies the page, compares the two positions, sums repeated signals, and applies Reed–Solomon correction. A minimum repeated-bit agreement is required; failed correction or low agreement returns no ID.

This is an initial implementation, not the final language in the brief: it has no distinctive corner anchors and its regular cell structure is not organic spread spectrum. It relies on visible page boundaries, assumes upright orientation, and has not been validated against physical prints or phone photos. Parameters are shared in `config.py`. The seed is fixed and public; this is not cryptographic protection.

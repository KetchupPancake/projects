# Shared Workspace — Mission

Filed 2026-11-08, from the mission walk with KetchupPancake. Second pass,
revised the same day per KetchupPancake's rulings on the four reviews and
the ghost examinations; approved by KetchupPancake for filing.

**Purpose.** The common ground — a conglomeration of two layers. The
cloud layer is the open stuff: the shared storage and compute all of
Hydra can access. The local layer is what KetchupPancake can muster together for
Cora at home. Together they are the one place where KetchupPancake and every
agent share the same memory, so the whole system works from a single
record instead of from what any one machine or chat happens to
remember. If it isn't in the workspace, it isn't shared truth.

**The two layers.** *Cloud:* the open layer — the Dropbox record (the
brief, standing rules, project state files, card corpus, decisions),
GitHub (all our code, commits and repos live there), and the other
shared assets; the eval-data repo Hydra needs will live
here too. Everything in the shared class is reachable by all of Hydra.
The workspace runs three classes — public, shared among the agents,
and private — and the private class is not stored here at all: it
lives under the Vault, on Cora's layer. *Local:* the home lab brain — Cora's own stores, holding what
stays home; Studio's media library lives on this side, on Cora. Ideally Cora gets a NAS / RAG of her own: a real local
brain, not scattered folders. Private work lives on this layer and
does not cross to the cloud side.

**How it stays trustworthy.** One writer for the index and state files
— Joy, since 2026-11-06, when KetchupPancake moved the duty from Joi — so the
record never forks. Every agent authors new files under its own prefix
and never edits another agent's files; corrections go in as siblings.
Nothing is deleted: old versions move to /99-SUPERSEDED. Legacy folders
are read-only. Two folders in the tree, sealed/ and finances/, are
private-class: they sit under the Vault's lock, are never opened from
the workspace, and are not part of the shared record. The record —
index, state, cards — is text only, and no secrets, ever. The roster
lives here too: every agent, box, lane and subscription, with its
status and operator — the system's own phone book, kept by the
single writer.

**Its place in the system.** Every node reads from the workspace and
writes back to it: Hydra's routing notes, The Still's cards, Academy's
pointers, the mission statements this walk is producing. The workspace
is the floor all the nodes stand on — which is why its own
observability is the index itself: INDEX, STATE and NEEDS-OPERATOR are its
board, the operator's queue of what needs his eyes.

**Good looks like.** Any agent — or KetchupPancake — can land cold and learn the
true state of every project from the workspace alone. Nothing important
lives only in one chat, one machine, or one model's memory. And the
rules of the floor are few, written down, and the same for everyone.

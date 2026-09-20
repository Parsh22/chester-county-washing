# Photos

Every image in here is a **real photo of a real job**. There are no
placeholders and no stock pictures — if a service has no photo, the site
shows an icon instead of faking one.

Right now that's one townhouse deck, shot twice.

```
jobs/deck-post-before.jpg   jobs/deck-post-after.jpg
jobs/deck-rail-before.jpg   jobs/deck-rail-after.jpg
```

## Adding a job

Phone before/after shots usually come out as **one wide image with a white
gap down the middle**. `import_photos.py` handles that for you: it finds the
gap, splits the image in two, trims the edges, crops to 4:3 and writes
optimised JPEGs.

```bash
python import_photos.py "~/Desktop/Before&After 3.png" driveway-main
```

That writes `jobs/driveway-main-before.jpg` and `jobs/driveway-main-after.jpg`
at 1200×900, around 100 KB each.

If your photo is a single picture rather than a side-by-side pair, add
`--no-split` and you'll get one file named exactly after the slug.

`import_photos.py` needs Pillow (`pip install Pillow`). The site itself
doesn't, which is why it isn't in `requirements.txt`.

Then add it to `WORK` in `config.py`:

```python
WORK = [
    {
        "title": "A driveway in Downingtown",
        "service": "driveway",          # a key from SERVICES
        "town": "Downingtown",
        "summary": "One or two sentences about the job.",
        "shots": [
            {
                "label": "By the garage",
                "note": "What the reader should look at.",
                "before": "photos/jobs/driveway-main-before.jpg",
                "after": "photos/jobs/driveway-main-after.jpg",
            },
        ],
    },
    # ...the existing deck entry
]
```

The home page picks it up with no template changes.

## Shooting pairs that work

The two photos sit side by side with **Before** and **After** labels, so they
need to look like the same place:

- **Same spot, same angle.** Mark where you stand before you start. Matching
  framing is what sells it.
- **Same time of day**, ideally the same visit. A sunny "after" against an
  overcast "before" reads as a lighting trick.
- **Shoot the before first** — easy to forget once you've started.
- **Landscape orientation.** Portrait gets cropped hard into a 4:3 slot.
- **Get in close on the thing that changed.** A whole-house shot hides the
  difference; a rail or a post base shows it.

## Permission

Ask the homeowner before putting their property on the site, and keep house
numbers, license plates and windows out of frame. A quick "mind if we put
this on our page?" while you're packing up is enough.

from datetime import datetime
from typing import Final

import genanki

# Constants
deck_name: Final[str] = ""
cards: list[tuple[str, str]] = []

# Define an Anki note model
model_id: Final[int] = 123456
model = genanki.Model(
    model_id,
    "Simple Model",
    fields=[
        {"name": "Directory"},
        {"name": "Description"},
    ],
    templates=[
        {
            "name": "Card 1",
            "qfmt": "{{Directory}}",
            "afmt": "{{Description}}",
        },
        {
            "name": "Card 2",
            "qfmt": "{{Description}}",
            "afmt": "{{Directory}}",
        },
    ],
)

# Generate Anki cards and add them to a deck
deck_id: Final[int] = 2059400110
deck = genanki.Deck(deck_id, deck_name)

for dir_name, description in cards:
    note = genanki.Note(model=model, fields=[dir_name, description])
    deck.add_note(note)

# Save the deck to an Anki package (*.apkg) file
current_time = datetime.now().strftime("%d-%m-%Y_%H-%M-%s")
genanki.Package(deck).write_to_file(f"{current_time}.apkg")

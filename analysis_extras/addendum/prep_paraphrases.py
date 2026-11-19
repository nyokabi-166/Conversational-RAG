"""Build the paraphrase pilot dataset from the 15 held-out questions.

Each question keeps its original wording (variant 0) and gets two rewordings
(variants 1 and 2). The ground truth is copied unchanged from heldout_questions.csv.
Writes analysis_extras/addendum/paraphrase_dataset.csv. No API calls.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "analysis_extras" / "final" / "heldout_questions.csv"
OUT = Path(__file__).resolve().parent / "paraphrase_dataset.csv"

PARA = {
    "H01": [
        "On a domestic flight run by Kenya Airways in Business Class, what is the checked baggage limit in pieces and weight?",
        "Business Class, domestic, Kenya Airways operated: how many bags can I check and how heavy can they be?",
    ],
    "H02": [
        "How much checked baggage is free in Business Class on a Kenya Airways flight inside Africa?",
        "I am flying Business Class within Africa on a Kenya Airways flight. What checked bags can I take for free?",
    ],
    "H03": [
        "Which internet speed and browser versions do I need to use Msafiriconnect?",
        "What are the minimum connection speed and supported browsers for Msafiriconnect?",
    ],
    "H04": [
        "How much is the MEDA (Airport Medical Review) fee one way, for local and international flights?",
        "What does Kenya Airways charge for the Airport Medical Review, on a local flight and on an international flight?",
    ],
    "H05": [
        "Does a seat bought for a corpulent passenger come with its own free checked baggage allowance?",
        "If I pay for an additional seat because of my size, do I get extra free checked baggage with it?",
    ],
    "H06": [
        "What is the rule if a passenger changes how they travel without getting Kenya Airways' agreement?",
        "If someone switches their transportation without Kenya Airways agreeing to it, what happens?",
    ],
    "H07": [
        "Is it allowed to take fragile musical instruments or valuable delicate equipment into the cabin when they are over the normal cabin baggage limits?",
        "My musical instrument is too big for normal cabin baggage. Can it still travel in the cabin?",
    ],
    "H08": [
        "Who can collect checked baggage, and what should someone do if they have lost the baggage check and identification tag?",
        "Who has the right to receive checked baggage at arrival, and what happens when the baggage check and tag cannot be shown?",
    ],
    "H09": [
        "What actions can Kenya Airways take when a passenger's behaviour on board puts the aircraft at risk, blocks the crew, or disturbs other passengers?",
        "If a passenger behaves in a way that endangers the plane or upsets others on board, what can Kenya Airways do?",
    ],
    "H10": [
        "What are the three website policies shown at the top of the Legal Information page?",
        "Which three policies appear first on the Kenya Airways Legal Information page?",
    ],
    "H11": [
        "Can I change a booking online if I bought it from a travel agent or another website?",
        "Is it possible to modify a reservation online when it was made through a travel agent or a third-party site?",
    ],
    "H12": [
        "What can happen if a passenger is not at the boarding gate at the time given at check-in?",
        "If I get to the boarding gate after the time I was told at check-in, what might Kenya Airways do?",
    ],
    "H13": [
        "How much does Kenya Airways charge to rent medical escort equipment?",
        "What is the price to lease medical escort equipment from Kenya Airways?",
    ],
    "H14": [
        "How much is the cancellation fee on a Business Best Buy fare?",
        "What do I pay to cancel a Business Best Buy ticket?",
    ],
    "H15": [
        "How many Asante miles will I earn flying Economy from Nairobi to London?",
        "What is the number of Asante miles earned on an Economy Nairobi to London flight?",
    ],
}

with SRC.open(encoding="utf-8-sig", newline="") as handle:
    base = list(csv.DictReader(handle))
fields = list(base[0].keys())
rows = []
for row in base:
    cid = row["case_id"]
    original = dict(row)
    original["review_status"] = "reviewed"
    rows.append(original)
    for number, text in enumerate(PARA[cid], start=1):
        item = dict(row)
        item["case_id"] = f"{cid}_p{number}"
        item["question"] = text
        item["review_status"] = "reviewed"
        rows.append(item)

with OUT.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
print(f"Wrote {len(rows)} rows to {OUT}")

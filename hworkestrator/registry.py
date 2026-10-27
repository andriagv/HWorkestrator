"""What the bot can do. To add a subject or a skill, add an entry here."""

SUBJECTS = {
    "dsa": {
        "title": "მონაცემთა სტრუქტურები და ალგორითმები",
        "source": "moodle",
        "match": "სტრუქტურები და ალგორითმები",   # substring of the Moodle course name
    },
    "spss": {
        "title": "სტატისტიკური მოდელები და იმიტაცია SPSS-ით",
        "source": "moodle",
        "match": "SPSS",
    },
    "ai": {
        "title": "ხელოვნური ინტელექტის საფუძვლები",
        "source": "moodle",
        "match": "ხელოვნური ინტელექტ",
    },
    "infosec": {
        "title": "ინფორმაციული უსაფრთხოების საფუძვლები",
        "source": "drive",
        "skills": ["secwork", "latexwork"],     # optional: which skills to offer (default: all)
    },
}

SKILLS = {
    "cppwork": "💻 cppwork — ლექციის კოდები → Word",
    "latexwork": "📐 latexwork — ამოცანები → LaTeX + PDF",
    "jupiterwork": "📓 jupiterwork — დავალება → Jupyter notebook (.ipynb)",
    "secwork": "🔐 secwork — ინფ. უსაფრთხოება: ამოცანები + Python კოდი → Word",
}

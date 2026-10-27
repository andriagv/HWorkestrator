"""What the bot offers — the file to edit when adapting the bot to a student.

SUBJECTS: key -> {"title": shown in the bot and used as the course name in the document header,
                  "source": where its assignments come from / go to — a name in sources.SOURCES,
                  "match": (moodle) substring of the Moodle course name,
                  "skills": (optional) which skills to offer for it; default all}
SKILLS:   skill folder in hworkestrator/skills/ -> button label
"""

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

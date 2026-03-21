import os
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

db_host = os.environ.get("DB_HOST", "localhost")
db_name = os.environ.get("DB_NAME", "notes")
db_user = os.environ.get("DB_USER", "notes")
db_pass = os.environ.get("DB_PASS", "notes")

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"postgresql://{db_user}:{db_pass}@{db_host}:5432/{db_name}"
)

db = SQLAlchemy(app)


class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "created_at": self.created_at.isoformat() + "Z",
            "updated_at": self.updated_at.isoformat() + "Z",
        }


with app.app_context():
    db.create_all()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/notes")
def list_notes():
    date_str = request.args.get("date")
    if date_str:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
        notes = Note.query.filter(db.func.date(Note.created_at) == date).all()
    else:
        notes = Note.query.order_by(Note.created_at.desc()).all()
    return jsonify([n.to_dict() for n in notes])


@app.route("/api/notes", methods=["POST"])
def create_note():
    data = request.get_json()
    if not data or not data.get("title") or not data.get("content"):
        return jsonify({"error": "title and content are required"}), 400
    note = Note(title=data["title"], content=data["content"])
    db.session.add(note)
    db.session.commit()
    return jsonify(note.to_dict()), 201


@app.route("/api/notes/<int:note_id>")
def get_note(note_id):
    note = db.session.get(Note, note_id)
    if not note:
        return jsonify({"error": "not found"}), 404
    return jsonify(note.to_dict())


@app.route("/api/notes/<int:note_id>", methods=["PUT"])
def update_note(note_id):
    note = db.session.get(Note, note_id)
    if not note:
        return jsonify({"error": "not found"}), 404
    data = request.get_json()
    if data.get("title"):
        note.title = data["title"]
    if data.get("content"):
        note.content = data["content"]
    db.session.commit()
    return jsonify(note.to_dict())


@app.route("/api/notes/<int:note_id>", methods=["DELETE"])
def delete_note(note_id):
    note = db.session.get(Note, note_id)
    if not note:
        return jsonify({"error": "not found"}), 404
    db.session.delete(note)
    db.session.commit()
    return jsonify({"deleted": note_id})


@app.route("/health")
def health():
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

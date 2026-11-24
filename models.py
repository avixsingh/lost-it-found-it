"""Database models for Lost It, Found It."""
from datetime import datetime, timezone

import numpy as np
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.CheckConstraint("role IN ('student','faculty','admin')", name="ck_user_role"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="student", index=True)
    phone = db.Column(db.String(20))
    department = db.Column(db.String(100))
    is_active_account = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    items = db.relationship("Item", back_populates="reporter", lazy="dynamic",
                            foreign_keys="Item.reporter_id")
    claims = db.relationship("Claim", back_populates="claimant", lazy="dynamic",
                             foreign_keys="Claim.claimant_id")
    notifications = db.relationship("Notification", back_populates="user",
                                    lazy="dynamic", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):  # Flask-Login: deactivated accounts cannot log in
        return self.is_active_account

    @property
    def is_admin(self):
        return self.role == "admin"

    def unread_count(self):
        return self.notifications.filter_by(is_read=False).count()


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    items = db.relationship("Item", back_populates="category", lazy="dynamic")


class Item(db.Model):
    """A lost report or a found report (kind = 'lost' or 'found')."""
    __tablename__ = "items"
    __table_args__ = (
        db.CheckConstraint("kind IN ('lost','found')", name="ck_item_kind"),
        db.CheckConstraint(
            "status IN ('active','returned','closed','removed')", name="ck_item_status"),
        db.Index("ix_item_kind_status", "kind", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(5), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    brand = db.Column(db.String(60))
    colour = db.Column(db.String(40))
    # Private: never shown on public pages. Finder notes what only the owner would know.
    private_details = db.Column(db.Text)
    location = db.Column(db.String(120), nullable=False, index=True)
    event_date = db.Column(db.Date, nullable=False)
    image_filename = db.Column(db.String(100))
    status = db.Column(db.String(10), nullable=False, default="active", index=True)
    embedding = db.Column(db.LargeBinary)  # cached float32 vector
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    category = db.relationship("Category", back_populates="items")
    reporter = db.relationship("User", back_populates="items", foreign_keys=[reporter_id])
    claims = db.relationship("Claim", back_populates="item", lazy="dynamic",
                             cascade="all, delete-orphan")

    def get_embedding(self):
        if self.embedding is None:
            return None
        return np.frombuffer(self.embedding, dtype=np.float32)

    def set_embedding(self, vector):
        self.embedding = None if vector is None else np.asarray(vector, dtype=np.float32).tobytes()

    def match_text(self):
        """Text sent to the AI model (private details are deliberately excluded)."""
        parts = [self.title, self.description, self.category.name if self.category else "",
                 self.brand or "", self.colour or ""]
        return ". ".join(p for p in parts if p)


class Claim(db.Model):
    __tablename__ = "claims"
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('pending','approved','rejected','returned')", name="ck_claim_status"),
        db.UniqueConstraint("item_id", "claimant_id", name="uq_claim_item_claimant"),
    )

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False, index=True)
    claimant_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    # Private verification answer: visible only to claimant, item reporter and admin.
    verification_details = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(10), nullable=False, default="pending", index=True)
    decision_reason = db.Column(db.Text)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    reviewed_at = db.Column(db.DateTime)
    returned_at = db.Column(db.DateTime)

    item = db.relationship("Item", back_populates="claims")
    claimant = db.relationship("User", back_populates="claims", foreign_keys=[claimant_id])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    message = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(200))
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    user = db.relationship("User", back_populates="notifications")


class MatchSuggestion(db.Model):
    """Cached AI suggestion; the unique pair prevents duplicate suggestions."""
    __tablename__ = "match_suggestions"
    __table_args__ = (
        db.UniqueConstraint("lost_item_id", "found_item_id", name="uq_match_pair"),
    )
    id = db.Column(db.Integer, primary_key=True)
    lost_item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False, index=True)
    found_item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False, index=True)
    score = db.Column(db.Float, nullable=False)  # indicative similarity 0..1, not a probability
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    lost_item = db.relationship("Item", foreign_keys=[lost_item_id])
    found_item = db.relationship("Item", foreign_keys=[found_item_id])

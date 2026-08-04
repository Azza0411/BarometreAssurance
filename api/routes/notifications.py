"""Routes /api/notifications/* — cloche de notifications in-app."""

from flask import Blueprint, jsonify, request
from database.repository import (
    get_connection, get_notifications, count_unread_notifications,
    mark_notification_read, mark_all_notifications_read,
)

bp = Blueprint("notifications", __name__)


@bp.route("/api/notifications")
def list_notifications():
    unread_only = request.args.get("unread_only") == "1"
    conn = get_connection()
    try:
        return jsonify(get_notifications(conn, unread_only=unread_only))
    finally:
        conn.close()


@bp.route("/api/notifications/unread-count")
def unread_count():
    conn = get_connection()
    try:
        return jsonify({"count": count_unread_notifications(conn)})
    finally:
        conn.close()


@bp.route("/api/notifications/<int:notif_id>/read", methods=["POST"])
def read_one(notif_id):
    conn = get_connection()
    try:
        mark_notification_read(conn, notif_id)
        return jsonify({"ok": True})
    finally:
        conn.close()


@bp.route("/api/notifications/read-all", methods=["POST"])
def read_all():
    conn = get_connection()
    try:
        mark_all_notifications_read(conn)
        return jsonify({"ok": True})
    finally:
        conn.close()

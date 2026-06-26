from app.db.connection import init_db, close_db, ping_db

from app.db.admin_settings import (
    get_admin_pin_hash,
    upsert_admin_pin,
    get_default_theme,
    update_default_theme,
)

from app.db.branches import (
    create_branch,
    get_branch,
    get_branch_by_code,
    list_branches,
    update_branch,
    delete_branch,
)

from app.db.units import (
    create_unit,
    get_unit,
    get_unit_by_device_uuid,
    list_units,
    update_unit_last_seen,
    update_unit_status,
)

from app.db.packages import (
    create_package,
    get_package,
    list_packages,
    deactivate_package,
    update_package_price,
    get_package_price,
)

from app.db.sessions import (
    create_session,
    get_session,
    list_sessions,
    count_sessions,
    update_session,
    complete_session,
    get_active_pending_session,
    get_active_photo_session,
)

from app.db.payments import (
    save_payment,
    list_payments,
)

from app.db.bill_logs import (
    log_bill_accepted,
    list_bill_logs,
    get_session_total_inserted,
)

from app.db.photos import (
    save_photo,
    get_photo,
    list_photos,
    mark_photo_printed,
)

from app.db.print_jobs import (
    create_print_job,
    update_print_job_status,
    list_print_jobs,
)

from app.db.device_events import (
    log_device_event,
    list_device_events,
    count_device_events,
)

from app.db.expenses import (
    create_expense,
    list_expenses,
    get_branch_expense_summary,
)

from app.db.sync import (
    enqueue_sync,
    list_pending_sync,
    mark_sync_done,
    mark_sync_failed,
    get_sync_stats,
)

__all__ = [
    "init_db",
    "close_db",
    "ping_db",
    "get_admin_pin_hash",
    "upsert_admin_pin",
    "get_default_theme",
    "update_default_theme",
    "create_branch",
    "get_branch",
    "get_branch_by_code",
    "list_branches",
    "update_branch",
    "delete_branch",
    "create_unit",
    "get_unit",
    "get_unit_by_device_uuid",
    "list_units",
    "update_unit_last_seen",
    "update_unit_status",
    "create_package",
    "get_package",
    "list_packages",
    "deactivate_package",
    "update_package_price",
    "get_package_price",
    "create_session",
    "get_session",
    "list_sessions",
    "count_sessions",
    "update_session",
    "complete_session",
    "get_active_pending_session",
    "get_active_photo_session",
    "save_payment",
    "list_payments",
    "log_bill_accepted",
    "list_bill_logs",
    "get_session_total_inserted",
    "save_photo",
    "get_photo",
    "list_photos",
    "mark_photo_printed",
    "create_print_job",
    "update_print_job_status",
    "list_print_jobs",
    "log_device_event",
    "list_device_events",
    "count_device_events",
    "create_expense",
    "list_expenses",
    "get_branch_expense_summary",
    "enqueue_sync",
    "list_pending_sync",
    "mark_sync_done",
    "mark_sync_failed",
    "get_sync_stats",
]
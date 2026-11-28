from django.core.management.base import BaseCommand

from documents.services import purge_expired_documents


class Command(BaseCommand):
    help = "Delete uploaded documents that are past their retention window (DOCUMENT_RETENTION_HOURS)."

    def handle(self, *args, **options):
        count = purge_expired_documents(force=True)
        self.stdout.write(self.style.SUCCESS(f"Purged {count} expired document(s)."))

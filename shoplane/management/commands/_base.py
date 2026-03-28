"""
Shared utilities for analytics management commands.

Every command that accepts --source db|csv, --from/--to date range,
and --output stdout|csv --file <path> inherits from AnalyticsCommand
and implements run(options) -> (header, rows).
"""
import csv
from datetime import date

from django.core.management.base import BaseCommand, CommandError


class AnalyticsCommand(BaseCommand):
    """
    Base class for analytics commands.

    Subclasses must implement:
        run(options) -> (header: list[str], rows: list[list])
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            choices=["db", "csv"],
            default="db",
            help="Data source: 'db' queries the database directly (default); "
                 "'csv' reads from a previously exported CSV file.",
        )
        parser.add_argument(
            "--file",
            default=None,
            help="Path to the input CSV when --source csv, "
                 "or the output CSV when --output csv.",
        )
        parser.add_argument(
            "--output",
            choices=["stdout", "csv"],
            default="stdout",
            help="Output format: 'stdout' prints a table (default); "
                 "'csv' writes to --file.",
        )
        parser.add_argument(
            "--from",
            dest="date_from",
            default=None,
            help="Start date filter (YYYY-MM-DD, inclusive).",
        )
        parser.add_argument(
            "--to",
            dest="date_to",
            default=None,
            help="End date filter (YYYY-MM-DD, inclusive).",
        )

    def handle(self, *args, **options):
        header, rows = self.run(options)

        if options["output"] == "csv":
            path = options.get("file")
            if not path:
                raise CommandError("--file is required when --output csv.")
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(header)
                writer.writerows(rows)
            self.stdout.write(self.style.SUCCESS(f"Wrote {len(rows)} rows to {path}"))
        else:
            self._print_table(header, rows)

    def run(self, options):
        raise NotImplementedError

    def parse_date(self, value, param_name):
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise CommandError(
                f"Invalid date '{value}' for --{param_name}. Expected YYYY-MM-DD."
            )

    def apply_date_range(self, queryset, options, field="created_at"):
        date_from = self.parse_date(options.get("date_from"), "from")
        date_to = self.parse_date(options.get("date_to"), "to")
        if date_from:
            queryset = queryset.filter(**{f"{field}__date__gte": date_from})
        if date_to:
            queryset = queryset.filter(**{f"{field}__date__lte": date_to})
        return queryset

    def read_csv(self, options):
        path = options.get("file")
        if not path:
            raise CommandError("--file is required when --source csv.")
        try:
            with open(path, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                return list(reader)
        except FileNotFoundError:
            raise CommandError(f"File not found: {path}")

    def _print_table(self, header, rows):
        if not rows:
            self.stdout.write("(no data)")
            return
        col_widths = [
            max(len(str(header[i])), *(len(str(r[i])) for r in rows))
            for i in range(len(header))
        ]
        fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
        separator = "  ".join("-" * w for w in col_widths)
        self.stdout.write(fmt.format(*header))
        self.stdout.write(separator)
        for row in rows:
            self.stdout.write(fmt.format(*[str(v) for v in row]))

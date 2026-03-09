"use client";

interface SummaryData {
  total_transactions: number;
  total_credits: string;
  total_debits: string;
  starting_balance: string;
  ending_balance: string;
  date_range: { from: string; to: string };
  balance_errors: number;
  type_breakdown: Record<string, number>;
}

interface SummaryProps {
  data: SummaryData;
  csvUrl: string;
  onReset: () => void;
}

function formatCurrency(value: string): string {
  const num = parseFloat(value);
  return num.toLocaleString("en-AU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatDate(dateStr: string): string {
  if (!dateStr) return "";
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-AU", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

const TYPE_COLORS: Record<string, string> = {
  Card: "bg-blue-500/20 text-blue-300 border-blue-500/30",
  Deposit: "bg-green-500/20 text-green-300 border-green-500/30",
  Payout: "bg-orange-500/20 text-orange-300 border-orange-500/30",
  Adjustment: "bg-yellow-500/20 text-yellow-300 border-yellow-500/30",
  Conversion: "bg-purple-500/20 text-purple-300 border-purple-500/30",
  Transfer: "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
};

export default function Summary({ data, csvUrl, onReset }: SummaryProps) {
  const totalTypeTxns = Object.values(data.type_breakdown).reduce(
    (a, b) => a + b,
    0
  );

  return (
    <div className="mt-6 space-y-6">
      {/* Summary header */}
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-6">
        <div className="mb-5 flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-green-500/20">
            <svg
              className="h-4 w-4 text-green-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="m4.5 12.75 6 6 9-13.5"
              />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-white">Summary</h2>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
          <StatCard
            label="Total Transactions"
            value={data.total_transactions.toLocaleString()}
            color="text-white"
          />
          <StatCard
            label="Total Credits"
            value={`$${formatCurrency(data.total_credits)}`}
            color="text-green-400"
          />
          <StatCard
            label="Total Debits"
            value={`$${formatCurrency(data.total_debits)}`}
            color="text-red-400"
          />
          <StatCard
            label="Starting Balance"
            value={`$${formatCurrency(data.starting_balance)}`}
            color="text-gray-300"
          />
          <StatCard
            label="Ending Balance"
            value={`$${formatCurrency(data.ending_balance)}`}
            color="text-white"
          />
          <StatCard
            label="Date Range"
            value={`${formatDate(data.date_range.from)} — ${formatDate(data.date_range.to)}`}
            color="text-gray-300"
            small
          />
          <StatCard
            label="Balance Validation"
            value={
              data.balance_errors === 0
                ? "0 errors"
                : `${data.balance_errors} errors`
            }
            color={data.balance_errors === 0 ? "text-green-400" : "text-red-400"}
          />
        </div>
      </div>

      {/* Transaction type breakdown */}
      <div className="rounded-xl border border-gray-800 bg-gray-900 p-6">
        <h3 className="mb-4 text-sm font-medium uppercase tracking-wider text-gray-500">
          Transaction Types
        </h3>
        <div className="space-y-3">
          {Object.entries(data.type_breakdown).map(([type, count]) => {
            const percent = Math.round((count / totalTypeTxns) * 100);
            const colorClasses =
              TYPE_COLORS[type] || "bg-gray-500/20 text-gray-300 border-gray-500/30";
            return (
              <div key={type} className="flex items-center gap-3">
                <span
                  className={`inline-flex min-w-[100px] items-center justify-center rounded-md border px-2.5 py-1 text-xs font-medium ${colorClasses}`}
                >
                  {type}
                </span>
                <div className="flex-1">
                  <div className="h-2 rounded-full bg-gray-800">
                    <div
                      className="h-full rounded-full bg-gray-600 transition-all duration-500"
                      style={{ width: `${percent}%` }}
                    />
                  </div>
                </div>
                <span className="min-w-[80px] text-right text-sm text-gray-400">
                  {count.toLocaleString()} ({percent}%)
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex gap-4">
        <a
          href={csvUrl}
          download
          className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-green-600 to-emerald-600 px-6 py-4 text-base font-semibold text-white transition-all hover:from-green-500 hover:to-emerald-500 hover:shadow-lg hover:shadow-green-500/20"
        >
          <svg
            className="h-5 w-5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"
            />
          </svg>
          Download CSV
        </a>
        <button
          onClick={onReset}
          className="rounded-xl border border-gray-700 px-6 py-4 text-base font-medium text-gray-300 transition-all hover:border-gray-500 hover:bg-gray-900 hover:text-white"
        >
          Process Another
        </button>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
  small,
}: {
  label: string;
  value: string;
  color: string;
  small?: boolean;
}) {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-950/50 p-4">
      <p className="text-xs font-medium uppercase tracking-wider text-gray-500">
        {label}
      </p>
      <p
        className={`mt-1 font-semibold ${color} ${small ? "text-sm" : "text-xl"}`}
      >
        {value}
      </p>
    </div>
  );
}

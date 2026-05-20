"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Series = { name?: string; data: { x: string | number; y: number }[]; color?: string };
type ChartData = { kind: string; series: Series[] };

const COLORS = ["#60a5fa", "#f472b6", "#fbbf24", "#34d399", "#a78bfa", "#fb7185"];

export default function ChartArtifact({ data }: { data: ChartData }) {
  if (data.kind === "pie") {
    const first = data.series[0];
    if (!first) return null;
    const pieData = first.data.map((d) => ({ name: String(d.x), value: d.y }));
    return (
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={pieData} dataKey="value" nameKey="name" outerRadius={80} label>
              {pieData.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // Pivot series into a wide-format dataset by x.
  const allX = new Set<string | number>();
  data.series.forEach((s) => s.data.forEach((p) => allX.add(p.x)));
  const wide = Array.from(allX).map((x) => {
    const row: Record<string, string | number> = { x: String(x) };
    data.series.forEach((s) => {
      const found = s.data.find((p) => p.x === x);
      row[s.name || "value"] = found ? found.y : 0;
    });
    return row;
  });

  const ChartType = data.kind === "line" ? LineChart : BarChart;
  const SeriesType = data.kind === "line" ? Line : Bar;

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <ChartType data={wide}>
          <CartesianGrid stroke="#ffffff15" strokeDasharray="3 3" />
          <XAxis dataKey="x" stroke="#fff8" fontSize={11} />
          <YAxis stroke="#fff8" fontSize={11} />
          <Tooltip />
          <Legend />
          {data.series.map((s, i) => (
            <SeriesType
              key={i}
              type="monotone"
              dataKey={s.name || "value"}
              fill={s.color || COLORS[i % COLORS.length]}
              stroke={s.color || COLORS[i % COLORS.length]}
            />
          ))}
        </ChartType>
      </ResponsiveContainer>
    </div>
  );
}

import MoneyMap from "../src/components/graph/MoneyMap";

export default function Home() {
  return (
    <main style={{ minHeight: "100vh", backgroundColor: "#0b111e" }}>
      <MoneyMap initialAccountId="acc_1" />
    </main>
  );
}

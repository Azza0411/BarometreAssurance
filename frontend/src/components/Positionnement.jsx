import { useState, useEffect } from "react";
import ReactApexChart from "react-apexcharts";
import { bubble } from "../data/mockData";
import PageLayout from "../components/PageLayout";

export default function Positionnement() {
  const kpis = [
    { label: "Primes Totales", value: "4.85 MDT", sub: "exercice 2024" },
    { label: "Nombre d'Assureurs", value: "29", sub: "compagnies actives" },
    { label: "Croissance Moyenne", value: "+11.8%", sub: "vs 2023", pos: true },
    { label: "Ratio Combiné", value: "87.4%", sub: "moyenne secteur" },
  ];

  return (
    <PageLayout 
      title="Positionnement Concurrentiel" 
      kpis={kpis}
    >
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20, flex: 1 }}>

        <div style={{ background: "white", borderRadius: 12, padding: 24 }}>
          <h3 style={{ marginBottom: 16 }}>Top 10 Assureurs</h3>
          <p>Contenu du tableau ici...</p>
        </div>

        <div style={{ background: "white", borderRadius: 12, padding: 24 }}>
          <h3 style={{ marginBottom: 16 }}>Matrice de Positionnement</h3>
          <p>Graphique bubble ici...</p>
        </div>

        <div style={{ background: "white", borderRadius: 12, padding: 24 }}>
          <h3 style={{ marginBottom: 16 }}>Comparaison</h3>
          <p>Graphique bar ici...</p>
        </div>

      </div>
    </PageLayout>
  );
}
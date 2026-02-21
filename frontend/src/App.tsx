import { useState } from "react";
import FileUpload from "./components/FileUpload";
import FlightList from "./components/FlightList";
import type { Flight } from "./types";
import { estimateDelays } from "./api";

function App() {
  const [flights, setFlights] = useState<Flight[]>([]);
  const [error, setError] = useState<string>("");

  const handleFileProcessed = (processedFlights: Flight[]) => {
    setFlights(processedFlights);
  };

  const handleError = (message: string) => {
    setError(message);
  };

  const handleEstimateDelays = async () => {
    setError("");
    try {
      const results = await estimateDelays(flights);
      setFlights(results);
    } catch (err: any) {
      setError(err.message || "Error estimating delays");
    }
  };

  return (
    <main className="container">
      <div className="container-fluid py-5">
        <h1 className="display-5 fw-bold text-white">Flight Delay Estimator</h1>
      </div>

      <div className="card shadow-sm mb-4">
        <div className="card-body">
          <h5 className="card-title">Upload Flights</h5>
          <FileUpload
            onFileProcessed={handleFileProcessed}
            onError={handleError}
          />
        </div>
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      <FlightList flights={flights} onEstimate={handleEstimateDelays} />
    </main>
  );
}

export default App;

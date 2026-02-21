import { useState } from "react";
import FileUpload from "./components/FileUpload";
import FlightList from "./components/FlightList";
import type { Flight } from "./types";

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
    console.log("Sending to backend:", { flights });

    const mockBackendResponse = {
      flights: flights.map((flight) => ({
        ...flight,
        estimatedDelay: Math.floor(Math.random() * 121),
      })),
    };

    await new Promise((resolve) => setTimeout(resolve, 500));

    console.log("Received from backend:", mockBackendResponse);
    setFlights(mockBackendResponse.flights);
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

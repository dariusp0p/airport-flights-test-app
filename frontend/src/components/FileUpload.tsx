import type { ChangeEvent } from "react";
import type { Flight } from "../types";

interface FileUploadProps {
  onFileProcessed: (flights: Flight[]) => void;
  onError: (message: string) => void;
}

const FileUpload = ({ onFileProcessed, onError }: FileUploadProps) => {
  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    if (file.type !== "application/json") {
      onError("Invalid file type. Please upload a JSON file.");
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const text = e.target?.result;
        if (typeof text !== "string") {
          throw new Error("Failed to read file content.");
        }
        const data = JSON.parse(text);

        if (!data.flights || !Array.isArray(data.flights)) {
          throw new Error("Invalid JSON structure: 'flights' array not found.");
        }

        for (const flight of data.flights) {
          const requiredStringProps = [
            "flightNumber",
            "airline",
            "from",
            "to",
            "scheduledArrival",
          ];

          for (const prop of requiredStringProps) {
            if (typeof (flight as any)[prop] !== "string") {
              throw new Error(
                `Invalid or missing property '${prop}' in a flight object. Expected a string.`,
              );
            }
          }

          if (isNaN(new Date(flight.scheduledArrival).getTime())) {
            throw new Error(
              `Invalid date format for scheduledArrival in flight ${flight.flightNumber}.`,
            );
          }
        }

        const flightsWithInitialDelay = data.flights.map((flight: any) => ({
          ...flight,
          estimatedDelay: null,
        }));

        onFileProcessed(flightsWithInitialDelay);
        onError("");
      } catch (error) {
        if (error instanceof Error) {
          onError(`Error processing file: ${error.message}`);
        } else {
          onError("An unknown error occurred while processing the file.");
        }
        onFileProcessed([]);
      }
    };
    reader.readAsText(file);
  };

  return (
    <div className="mb-3">
      <label htmlFor="formFile" className="form-label">
        Expected format is JSON
      </label>
      <input
        className="form-control"
        type="file"
        id="formFile"
        accept="application/json"
        onChange={handleFileChange}
      />
    </div>
  );
};

export default FileUpload;

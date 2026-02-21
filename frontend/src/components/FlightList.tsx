import type { Flight } from "../types";

interface FlightListProps {
  flights: Flight[];
  onEstimate: () => void;
}

const FlightList = ({ flights, onEstimate }: FlightListProps) => {
  if (flights.length === 0) {
    return (
      <div className="card shadow-sm">
        <div className="card-body text-center">
          <p className="card-text text-muted">
            No flight data loaded. Upload a file to get started.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="card shadow-sm overflow-hidden">
      <div className="card-header d-flex justify-content-between align-items-center">
        <h5 className="mb-0">Flights</h5>
        <button className="btn btn-warning text-white" onClick={onEstimate}>
          Estimate Delays
        </button>
      </div>
      <div className="card-body p-0">
        <div className="table-responsive">
          <table className="table table-striped table-hover mb-0">
            <thead className="table-light">
              <tr>
                <th scope="col">Flight Number</th>
                <th scope="col">Airline</th>
                <th scope="col">From</th>
                <th scope="col">To</th>
                <th scope="col">Scheduled Arrival</th>
                <th scope="col">Estimated Delay (min)</th>
              </tr>
            </thead>
            <tbody>
              {flights.map((flight, index) => (
                <tr key={index}>
                  <td>{flight.flightNumber}</td>
                  <td>{flight.airline}</td>
                  <td>{flight.from}</td>
                  <td>{flight.to}</td>
                  <td>{new Date(flight.scheduledArrival).toLocaleString()}</td>
                  <td>
                    {flight.estimatedDelay === null ? (
                      <span className="text-muted">N/A</span>
                    ) : (
                      <span className="badge bg-warning text-dark">
                        {flight.estimatedDelay}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default FlightList;

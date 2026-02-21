export interface Flight {
  flightNumber: string;
  airline: string;
  from: string;
  to: string;
  scheduledArrival: string;
  estimatedDelay: number | null;
}
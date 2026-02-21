export async function estimateDelays(flights: any[]) {
  const response = await fetch("http://localhost:8000/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ flights }),
  });

  if (!response.ok) throw new Error("Failed to create job");
  const job = await response.json();

  let result;
  for (let i = 0; i < 20; i++) {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    const res = await fetch(`http://localhost:8000${job.resultUrl}`);
    if (res.ok) {
      result = await res.json();
      break;
    }
  }
  if (!result) throw new Error("Job did not finish in time");
  return result.results || [];
}
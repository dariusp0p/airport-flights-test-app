How it works: 
1. Data API s: Flight data API
               Weather data API
2. Delay Prediction Engine: 
        ML approach: train a simple ML model(like a Random Forest or XGBoost). 
            Input: Departure time, departure airport weather, Oradea weather, airline.
        Rule-based Approach: 
            If departing airport has heavy rain =>Add 15 mins delay.
            If departure was delayed by 20 mins => Add 20 mins to Oradea arrival. 
3. The reschedeuling algorithm:
    Safe landing interval(Only one plane can land every 10 mins) 
    The Logic: Flight A is predicted to be delayed by 20 minutes, pushing its arrival from 14:00 to 14:20.
               Flight B is originally scheduled to land at 14:25.
            Because 14:20 and 14:25 are too close, the tower comunicates to flight B to slow down to arrive to 14.30 instead 
    Tech implementation: Simple algorithm to give priority based on delay heavier planes, or low fuel.
# 3\_2 warm-cache timing comparison (ms)

Client: Python 3.12.6 + psycopg 3.3.6 (s32\_benchmark.py)  
Timer: time.perf\_counter() around execute()+fetchall()  
Machine: Muhirwa  
Session: 2026-10-13 12:08:18.733 CAT to 2026-10-13 12:09:13.447 CAT = 54.7 s

|query|table|median ms|min ms|max ms|
|-|-|-|-|-|
|Q1|energy\_readings\_3h|156.3|153.0|163.1|
|Q1|energy\_readings|174.3|158.3|231.7|
|Q1|energy\_readings\_week|163.8|160.5|178.9|
|Q2|energy\_readings\_3h|222.7|214.1|224.9|
|Q2|energy\_readings|218.7|210.9|243.4|
|Q2|energy\_readings\_week|272.8|257.8|286.4|
|Q3|energy\_readings\_3h|3,520.1|2,952.7|3,590.0|
|Q3|energy\_readings|1,002.4|990.0|1,064.8|
|Q3|energy\_readings\_week|913.7|867.5|1,007.9|
|Q4|energy\_readings\_3h|6.9|5.2|7.3|
|Q4|energy\_readings|2.7|1.8|3.0|
|Q4|energy\_readings\_week|1.8|1.8|2.3|
|Q5|energy\_readings\_3h|981.8|901.1|1,010.9|
|Q5|energy\_readings|803.2|796.7|821.7|
|Q5|energy\_readings\_week|797.8|759.9|825.4|

|query|energy\_readings\_3h|energy\_readings|energy\_readings\_week|fastest|fastest vs slowest|
|-|-|-|-|-|-|
|Q1|156.3|174.3|163.8|energy\_readings\_3h|1.12 x faster than energy\_readings|
|Q2|222.7|218.7|272.8|energy\_readings|1.25 x faster than energy\_readings\_week|
|Q3|3,520.1|1,002.4|913.7|energy\_readings\_week|3.85 x faster than energy\_readings\_3h|
|Q4|6.9|2.7|1.8|energy\_readings\_week|3.79 x faster than energy\_readings\_3h|
|Q5|981.8|803.2|797.8|energy\_readings\_week|1.23 x faster than energy\_readings\_3h|

Chunks touched

|query|energy\_readings\_3h|energy\_readings|energy\_readings\_week|
|-|-|-|-|
|Q1|9|2|1|
|Q2|57|8|2|
|Q3|225|29|5|
|Q4|57|8|2|
|Q5|225|29|5|




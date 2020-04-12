Json file created from https://covidactnow.org/us/ny/county/new_york_county.

The original data from the model only has data every four days: we will need to intrapolate the points of the three days in between.

For example, between 04/20 and 04/24, the two data points from the site is 35451 and 37794. After intrapolation, we can get

2020-04-20	35451
2020-04-21	36037
2020-04-22	36623
2020-04-23	37208
2020-04-24	37794

The available bed saturation point is also from the website: for New Yok, the number is currently 20420.
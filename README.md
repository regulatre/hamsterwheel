

# Hamster Wheel Speedometer

Yes you heard right, we're measuring how far and how fast the hamsters run each night =)


## Purpose

Data science is a hobby and a large part of my profession. By building things in my home lab, I gain experience in an environment where I can use the latest technology without any real risks. The systems I build in my lab give me the hands-on experience with emerging technologies, as well as a risk free environment to try things, solve problems, and come up with new ways to do things. All of that translates to higher productive and effectiveness in my professional work. 

## Project Overview

The goal is to measure two things: 1: Distance, and 2: Speed, of the hamsters using wheel speed sensors and home-grown software code to analyze the data. All data thus far is gleaned from simply measuring RPM (number of times the wheel turns per minute), which leads to MPH (miles per hour, which is easily calculated by multiplying RPM by each wheel's unique distance per revolution). 

The project has three main parts: measurement hardware, measurement software, and a data collection and  visualization backend. For visualization I use Grafana. For data persistence I use Elasticsearch. Logstash provides a convenient means of collecting the data, filtering it, and passing it to Elasticsearch for indexing, as well as a Kafka topic. The Kafka topic is just a little something extra I include in my data pipelines, so that I can set up event notifications, triggers, and things like that. I've set up alerts for other projects that notify me of network security events, electric grid outages/events, and so on. 

<img src="images/hamsterWheelSpeedometerDiagram1.png" alt="Overview Diagram" width="800">

## Grafana Statistics Dashboard
<img src="images/hamsterWheelStatisticsDay2partial.png" alt="Overview Diagram" width="800">

## Raspberry Pi with ADC HAT

The ADC Hat is a 16-bit ADS1115 module. I'm using two of the four inputs for speed measurement. I take advantage of the Raspberry Pi's built-in Wi-Fi, which eliminates the need for a wired network connection. The Pi module plugs into power, and the two speedometer wires lead to each of the two hamster habitats for data collection. 

<img src="images/hamsterPi.png" alt="Overview Diagram" width="400">


## Wheel Speed Sensors installed
Notice the tiny magnet that's glued to the wheel. As it spins around, this magnet passes by the coil, inducing a small current that is easily measured by the ADC

The wheel speed sensor is a simple inductive coil with about 100 turns. The coil runs back to the ADC input block, where it I have added an additional 1k pull-down resistor, which helps reduce noise and inductive reverberations. I affixed the sensor to the habitat in a way that doesn't leave the wires within reach of the hamster, which they would invariably chew on if within reach. During the calibration phase of the project, the kids and I took measurements of each wheel, and recorded the measurements on the yellow tape you see on the wheel. They did the experiments, and most of the writing. 

<img src="images/wheelSpeedSensorInstalled.png" alt="Overview Diagram" width="800">

## Inductor Coils

Breathing life back into old USB charger cables that got bent and no longer would charge. I snipped the USB ends off and just used the wire. They conveniently came with pre-installed ferrite chokes, which certainly won't hurt, and probably help prevent ambient EMI noise from inducing spurrious readings. 

<img src="images/hallEffectSensors.png" alt="Overview Diagram" width="400">

## Observations

The hamsters start their exercise about 10 minutes after the lights go out, and typically exercise about four hours each night. When one hamster starts running, the other tends to start too, although at times, the data seems to suggest that Fluff doesn't start significant exercise until after Cutie's wheel cools down for a while. Cutie's wheel does make a lot of racket and may be intimidating to Fluff. Future experiment: oil the wheel and see if this increases Fluff's activity. 

## Data Schema

Every time the wheel stops spinning for more than about 2 seconds, the current set of metrics for that wheel are summarized, packaged up, and sent to the log collection backend (Elasticsearch, via logstash). 

Individual messages look something like this: 

``` json
{
  "appUptimeSeconds": 2778,
  "runTimeSeconds": 13.9,
  "mph": 1.546,
  "timestamp": 1575351483019,
  "rpm": 83.739,
  "statsPeriod": 21999,
  "lastRevolutionMillis": 794,
  "@version": "1",
  "@timestamp": "2019-12-03T05:38:03.057Z",
  "totalRevolutions": 23,
  "queuedms": 0,
  "mph_max": 1.976,
  "AvgAmtChange": 9.027,
  "analogIndex": 2,
  "totalInches": 448.5,
  "host": "x.x.x.x"
}

```

Which Elasticsearch happily consumes with basically no effort at all. In Grafana then, I've built a dashboard that connects to Elasticsearch, and aggregates the data. Data from each of the two wheels is separated by the analogIndex field, which corresponds to the ADC HAT input index (remember there are four). The wheel speed probes each attach to an analog input. This field lets me distinguish metrics for one hamster versus the other. 

## Calibration

Before "going live" the kids and I drew up the project on paper and discussed each component. We each took turns taking measurements of the wheels, and installing the wheel speed sensor magnets. The measurements we took included: radius, and circumfrance. We checked, and double-checked the most important metric (circumfrance) by rolling the wheel on the table next to a tape measure, and writing down each measurement, throwing out the bad ones, and averaging the most accurate ones. 

In the application, a wide range of calibrations, and logic had to be added to carefully measure each revolution once and only once. The signal coming into the ADC is a typical impulse signal, where the waves grow rapidly to a peak and then decline rapidly. By defining a trigger threshold, and trigger direction, I wrote code that detects each revolution very effectively and thus far doesn't show any signs of invalid data (we'll see in a few weeks when I have more data to look at too).

## TODO

1. Create a systemd service unit to run the application
1. Experiment with different ways to increase the hamsters' activity levels, such as quieting down their wheels (so they aren't scared to run in them), rearranging the layout, moving them away from eachother (prevent one from being scared by the other's noise), various foods, ...



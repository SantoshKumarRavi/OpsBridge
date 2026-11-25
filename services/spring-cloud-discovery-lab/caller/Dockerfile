FROM eclipse-temurin:21-jre
WORKDIR /app
COPY target/discovery-caller-1.0.0.jar /app/app.jar
EXPOSE 8090
ENTRYPOINT ["java", "-jar", "/app/app.jar"]

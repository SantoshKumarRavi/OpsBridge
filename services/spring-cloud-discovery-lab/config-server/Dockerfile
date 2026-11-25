FROM eclipse-temurin:21-jre
WORKDIR /app
COPY target/config-server-1.0.0.jar /app/app.jar
EXPOSE 8888
ENTRYPOINT ["java", "-jar", "/app/app.jar"]

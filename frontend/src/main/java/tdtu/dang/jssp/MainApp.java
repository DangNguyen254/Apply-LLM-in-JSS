package tdtu.dang.jssp;
import javafx.application.Application;
import javafx.fxml.FXMLLoader;
import javafx.scene.Parent;
import javafx.scene.Scene;
import javafx.stage.Stage;

public class MainApp extends Application{
    public static void main(String[] args) {
        launch(args);
    }

    public void start(Stage primaryStage){
        try {
            // Create an FXMLLoader to find FXML file.
            FXMLLoader loader = new FXMLLoader(getClass().getResource("/tdtu/dang/jssp/views/MainView.fxml"));

            // Load the FXML to create the layout.
            Parent root = loader.load();

            // Create a Scene containing that layout.
            Scene scene = new Scene(root);

            // Set the window title.
            primaryStage.setTitle("JSSP Solver with LLM");

            // fill screen without hide the menu bar
            primaryStage.setMaximized(true);

            // Place the Scene onto the Stage.
            primaryStage.setScene(scene);
            

            // Show the Stage (make the window visible).
            primaryStage.show();

        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
package tdtu.dang.jssp;

import javafx.application.Application;
import javafx.fxml.FXMLLoader;
import javafx.scene.Parent;
import javafx.scene.Scene;
import javafx.stage.Stage;
import tdtu.dang.jssp.controllers.LoginViewController;
import tdtu.dang.jssp.controllers.MainViewController;
import tdtu.dang.jssp.services.ApiClient;

import java.io.IOException;

public class MainApp extends Application {
    
    private Stage primaryStage;
    private Scene loginScene;
    private Scene mainScene;
    
    private LoginViewController loginViewController;
    private MainViewController mainViewController;

    public static void main(String[] args) {
        launch(args);
    }

    @Override
    public void start(Stage primaryStage) {
        this.primaryStage = primaryStage;
        
        // We use one shared ApiClient for the whole app
        ApiClient sharedApiClient = new ApiClient();

        try {
            // Load Login View
            FXMLLoader loginLoader = new FXMLLoader(getClass().getResource("/tdtu/dang/jssp/views/LoginView.fxml"));
            Parent loginRoot = loginLoader.load();
            this.loginViewController = loginLoader.getController();
            this.loginViewController.setMainApp(this);
            this.loginViewController.setApiClient(sharedApiClient);
            this.loginScene = new Scene(loginRoot, 400, 400); // Fixed size for login

            // Load Main View
            FXMLLoader mainLoader = new FXMLLoader(getClass().getResource("/tdtu/dang/jssp/views/MainView.fxml"));
            Parent mainRoot = mainLoader.load();
            this.mainViewController = mainLoader.getController();
            this.mainViewController.setMainApp(this); // Pass MainApp to main controller
            
            // Note: We don't set the ApiClient or username until AFTER login
            
            this.mainScene = new Scene(mainRoot);

            // Set the window title
            primaryStage.setTitle("JSSP Orchestrator");
            
            // Show the Login Scene first
            primaryStage.setScene(loginScene);
            primaryStage.show();

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    /**
     * Called by LoginViewController after a successful login.
     */
    public void showMainView(String username, ApiClient apiClient) {
        // Pass the shared, authenticated ApiClient to the main controller
        mainViewController.onLoginSuccess(apiClient, username);
        
        // Switch the scene
        primaryStage.setScene(mainScene);
        primaryStage.setMaximized(true); // Maximize the main window
    }

    /**
     * Called by MainViewController on logout.
     */
    public void showLoginView() {
        // Clear password field for security
        loginViewController.clearPassword();
        
        // Switch the scene
        primaryStage.setScene(loginScene);
        primaryStage.setMaximized(false); // Un-maximize
        primaryStage.setWidth(400);
        primaryStage.setHeight(400);
        primaryStage.centerOnScreen();
    }
}